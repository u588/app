import os
# This guide can only be run with the torch backend.
os.environ["KERAS_BACKEND"] = "torch"

import torch
import keras
from keras import layers
import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
from sklearn.preprocessing import Normalizer

encoding_dim = 10  # 32 floats -> compression of factor 24.5, assuming the input is 784 floats
# This is our input image
input_img = keras.Input(shape=(70,))
# "encoded" is the encoded representation of the input
encoded = layers.Dense(encoding_dim, activation='relu')(input_img)
# "decoded" is the lossy reconstruction of the input
decoded = layers.Dense(70, activation='sigmoid')(encoded)
# This model maps an input to its reconstruction
autoencoder = keras.Model(input_img, decoded)
# This model maps an input to its encoded representation
encoder = keras.Model(input_img, encoded)
# This is our encoded (32-dimensional) input
encoded_input = keras.Input(shape=(encoding_dim,))
# Retrieve the last layer of the autoencoder model
decoder_layer = autoencoder.layers[-1]
# Create the decoder model
decoder = keras.Model(encoded_input, decoder_layer(encoded_input))
autoencoder.compile(optimizer='adam', loss='binary_crossentropy')

a = pd.read_excel('g:/1/2/st000001.xlsx')
b = pd.read_excel('g:/1/2/st000001pcb5.xlsx')
c = pd.read_excel('g:/1/2/st000001pcb13.xlsx')


i = 0
qq = pd.DataFrame((a[a.datetime>=b.loc[i][3:5][1]][a.datetime<=b.loc[i][3:5][0]].reset_index()[['open','close','high','low','mea']]).stack().values).T
while i < len(b):
    print(i)
    df = a[a.datetime>=b.loc[i][3:5][1]][a.datetime<=b.loc[i][3:5][0]].reset_index()[['open','close','high','low','mea']]
    aa = pd.DataFrame(df.stack().values).T
    qq = pd.concat([qq,aa])
    i = i + 1
 
nor = Normalizer(norm='l2')
x_train = nor.fit_transform(qq[1:65])
x_test = nor.fit_transform(qq[65:])


autoencoder.fit(x_train, x_train,
                epochs=10,
                batch_size=20,
                shuffle=True,
                validation_data=(x_test, x_test))