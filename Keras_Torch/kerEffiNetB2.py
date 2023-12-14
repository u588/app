import os
os.environ["KERAS_BACKEND"] = "torch"

import torch
import keras

from keras.applications import EfficientNetV2S
model = EfficientNetV2S(weights='imagenet')

keras.applications.EfficientNetB2(
    include_top=True,
    weights="imagenet",
    input_tensor=None,
    input_shape=None,
    pooling=None,
    classes=1000,
    classifier_activation="softmax",
    **kwargs
)
