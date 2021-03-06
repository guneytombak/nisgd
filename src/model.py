import sys
import numpy as np

import torch
from torch import optim
import torch.nn as nn
import torch.nn.functional as F
import copy

import wandb

from src.utils import ActivType, LossType, TaskType

class Net(nn.Module):
    """
    A standard neural network takes the layer numbers as
    input_size -> hidden_size -> output_size
    input_size and output_size are integers
    whereas hidden_size can be integer or a list containing integers
    activation is the activation function of the network

    If any combination of layer sizes are not given, 
    They are going to be extracted from Container class cfg
    """
    def __init__(self, cfg=None, input_size=None, 
                 hidden_size=None, output_size=None,
                 activation=None, task_type=None, verbose=True):
        super(Net, self).__init__()
        
        ins, his, ous, acv = default_model(input_size, hidden_size, output_size, 
                                           activation, cfg)
        if verbose:
            print(f'Model dims are {ins}->{his}->{ous}')
        
        if not isinstance(his, list):
            his = [his]
        
        self.fc_hid = list()
        
        self.fc_in = nn.Linear(ins, his[0])
        
        for i in range(len(his)-1):
            self.fc_hid.append(nn.Linear(his[i], his[i+1]))
        
        self.fc_hid = nn.ModuleList(self.fc_hid)
        self.fc_out = nn.Linear(his[-1], ous)
        
        self.act = select_activation(acv)

    def forward(self, x):
        """
        x_0 = vector(x)
        x_1 = act(W_1@x_0 + b_1)
        ...
        output = W_f@x + b_f
        """
        x = x.view(x.shape[0], -1)
        x = self.fc_in(x)
        x = self.act(x)
        
        for i in range(len(self.fc_hid)):
            x = self.fc_hid[i](x)
            x = self.act(x)
        
        output = self.fc_out(x)

        return output
    
    def initialize(self):
        """
        Initialize the network weights according to Xavier uniform distribution. 
        """
        nn.init.xavier_uniform_(self.fc_in.weight)
        for i in range(len(self.fc_hid)):
            nn.init.xavier_uniform_(self.fc_hid[i].weight)
        nn.init.xavier_uniform_(self.fc_out.weight)
        
    def get_weights(self):
        """
        Get weights as a vector:
        [W_1,W_2,...,W_f]
        """
        w = self.fc_in.weight.cpu().view(-1).clone()
        for i in range(len(self.fc_hid)):
            w_i = self.fc_hid[i].weight.cpu().view(-1).clone()
            w = torch.cat((w, w_i), 0)
        w_out = self.fc_out.weight.cpu().view(-1).clone()
        return torch.cat((w, w_out), 0)

    def get_biases(self):
        """
        Get weights as a vector:
        [b_1,b_2,...,b_f]
        """
        b = self.fc_in.bias.cpu().view(-1).clone()
        for i in range(len(self.fc_hid)):
            b_i = self.fc_hid[i].bias.cpu().view(-1).clone()
            b = torch.cat((b, b_i), 0)
        b_out = self.fc_out.bias.cpu().view(-1).clone()
        return torch.cat((b, b_out), 0)

    def get_wb(self):
        """
        Get all parameters (weights and biases) as a vector:
        [W_1,b_1,W_2,b_2,...,W_f,b_f]
        """
        w_in = self.fc_in.weight.cpu().view(-1).clone()
        b_in = self.fc_in.bias.cpu().view(-1).clone()
        wb = torch.cat((w_in, b_in), 0)
        for i in range(len(self.fc_hid)):
            w_i = self.fc_hid[i].weight.cpu().view(-1).clone()
            b_i = self.fc_hid[i].bias.cpu().view(-1).clone()
            wb_i = torch.cat((w_i, b_i), 0)
            wb = torch.cat((wb, wb_i), 0)
        w_out = self.fc_out.weight.cpu().view(-1).clone()
        b_out = self.fc_out.bias.cpu().view(-1).clone()
        wb_out = torch.cat((w_out, b_out), 0) 
        return torch.cat((wb, wb_out), 0)
    
    def get_grads(self):
        """
        Get gradients of all parameters (weights and biases) as a vector:
        DelL / Del [W_1,b_1,W_2,b_2,...,W_f,b_f]
        """
        gw_in = self.fc_in.weight._grad.cpu().view(-1).clone()
        gb_in = self.fc_in.bias._grad.cpu().view(-1).clone()
        g = torch.cat((gw_in, gb_in), 0)
        for i in range(len(self.fc_hid)):
            gw_i = self.fc_hid[i].weight._grad.cpu().view(-1).clone()
            gb_i = self.fc_hid[i].bias._grad.cpu().view(-1).clone()
            g_i = torch.cat((gw_i, gb_i), 0)
            g = torch.cat((g, g_i), 0)
        gw_out = self.fc_out.weight._grad.cpu().view(-1).clone()
        gb_out = self.fc_out.bias._grad.cpu().view(-1).clone()
        g_out = torch.cat((gw_out, gb_out), 0) 
        return torch.cat((g, g_out), 0)

def default_model(input_size, hidden_size, output_size, 
                  activation, cfg):
    """
    Get default model parameters defined in Container cfg
    """
    
    if cfg is not None:
    
        if input_size is None:
            input_size = cfg.input_size
        
        if hidden_size is None:
            hidden_size = cfg.hidden_size
            
        if output_size is None:
            output_size = cfg.output_size
            
        if activation is None:
            activation = cfg.activ_type
        
    return input_size, hidden_size, output_size, activation

def select_activation(activation):
    """
    Select the activation function according to the given ActiveType object.
    """
    
    if activation == ActivType.GELU:
        return nn.GELU()
    elif activation ==  ActivType.RELU:
        return nn.ReLU()
    elif activation ==  ActivType.SIGMOID:
        return nn.Sigmoid()
    elif activation ==  ActivType.ID:
        return nn.Identity()
    else:
        print(f'No activation provided for \"{activation}\", using no activation.')
        return nn.Identity()
