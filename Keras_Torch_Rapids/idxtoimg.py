# import tensorflow.examples.tutorials.mnist.input_data as input_data
import torch
from torch import nn
from torch.utils.data import DataLoader
from torchvision import datasets
from torchvision.transforms import ToTensor
import matplotlib.pyplot as plt
import numpy as np

# MNIST_data_folder = 'MNIST_data_folder'
# mnist = input_data.read_data_sets(MNIST_data_folder, one_hot=False) #MNIST_data_folder是数据集的目录
# imgs, labels = mnist.test.images, mnist.test.labels #生成测试集图片
# imgs, labels = mnist.validation.images, mnist.validation.labels  #生成验证集图片
training_data = datasets.FashionMNIST(
    root="g:/1/2",
    train=True,
    download=True,
    transform=ToTensor(),
)

# Download test data from open datasets.
test_data = datasets.FashionMNIST(
    root="g:/1/2",
    train=False,
    download=True,
    transform=ToTensor(),
)


plt.imshow((test_data[0][0]*255)[0], cmap='Grapys')
