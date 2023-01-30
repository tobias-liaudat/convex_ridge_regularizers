import torch
from torch import nn
import torch.nn.utils.parametrize as P

import math
from math import sqrt

import numpy as np

class MultiConv2d(nn.Module):
    def __init__(self, channels, kernel_size=3, padding=1, bias=False):
        super().__init__()
        # parameters
        self.padding = padding
        self.kernel_size = kernel_size
        self.channels = channels

        # convolutionnal layers
        self.conv_layers = nn.ModuleList()
        for i in range(len(channels) - 1):
                self.conv_layers.append(nn.Conv2d(in_channels=channels[i], out_channels=channels[i+1], kernel_size=kernel_size, padding=padding, bias=bias))
                P.register_parametrization(self.conv_layers[-1], "weight", ZeroMean())
        
        # scale the filters to ensure spectral norm of one at init
        self.initSN()

    def forward(self, x, sn=True):
        return(self.convolution(x))

    def spectral_norm(self, n_power_iterations=10, size=40):
        u = torch.empty((1, self.conv_layers[0].weight.shape[1], size, size), device=self.conv_layers[0].weight.device).normal_()
        with torch.no_grad():
            for _ in range(n_power_iterations):
                # In this loop we estimate the eigen vector u corresponding to the largest eigne value of W^T W
                v = normalize(self.convolutionNoBias(u))
                u = normalize(self.transpose(v))
                if n_power_iterations > 0:
                    # See above on why we need to clone
                    u = u.clone()
                    v = v.clone()
        
            # The largest eigen value can now be estimated in a differentiable way
            cur_sigma = torch.sum(u * self.transpose(v))

            return cur_sigma


    def initSN(self):
        with torch.no_grad():
            cur_sn = self.spectral_norm()
            for conv in self.conv_layers:
                conv.weight.data = conv.weight.data/(cur_sn**(1/len(self.conv_layers)))   

    def convolution(self, x):
        for conv in self.conv_layers:
            x = nn.functional.conv2d(x, conv.weight, padding=self.padding)
            
        return(x)

    def convolutionNoBias(self, x):
        for conv in self.conv_layers:
            x = nn.functional.conv2d(x, conv.weight, padding=self.padding)
        return(x)

    def transpose(self, x):
        for conv in reversed(self.conv_layers):
            # there are two variants to implement the transpose of a conv with 0 padding in torch
            # x = nn.functional.conv2d(x.flip(2,3), conv.weight.permute(1, 0, 2, 3), padding=self.padding).flip(2, 3)
            weight = conv.weight
            x = nn.functional.conv_transpose2d(x, weight, padding=conv.padding, groups=conv.groups, dilation=conv.dilation)
        return(x)
    


def normalize(tensor, eps=1e-12):
    norm = float(torch.sqrt(torch.sum(tensor**2)))
    norm = max(norm, eps)
    ans = tensor / norm
    return ans

# zero mean kernel parametrization
class ZeroMean(nn.Module):
    def forward(self, X):
        return(X - torch.mean(X, dim=(1,2,3)).unsqueeze(1).unsqueeze(2).unsqueeze(3))

                