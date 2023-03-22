#!/usr/bin/env python3

# Binary image classification:
#  https://towardsdatascience.com/binary-image-classification-in-pytorch-5adf64f8c781
# Uses dataset https://www.kaggle.com/datasets/biaiscience/dogs-vs-cats

# Alternatively, training for 10 classes with RGB images from CIFAR
#  https://pytorch.org/tutorials/beginner/blitz/cifar10_tutorial.html
# which references this (1-channel mono images):
#  https://pytorch.org/tutorials/recipes/recipes/defining_a_neural_network.html

# create directories:
#   training
#     cat
#     dog
#   validation
#     cat
#     dog

import argparse
import sys
import torch
import torchvision
from torchvision import datasets, transforms

# Command line parameters
parser = argparse.ArgumentParser(description='Detect scanned forms vs clinical images')
parser.add_argument('-d', '--debug', action="store_true", help='debug')
parser.add_argument('-e', '--epochs', dest='epochs', action="store", help='number of epoch runs during training')
parser.add_argument('-m', '--model', dest='modelfile', action="store", help='filename to load/save trained model')
parser.add_argument('-t', '--traindir', dest='traindir', action="store", help='directory of training images')
parser.add_argument('-v', '--valdir', dest='valdir', action="store", help='directory of validation images')
args = parser.parse_args()

n_epochs = int(args.epochs) if args.epochs else 10
model_file = args.modelfile if args.modelfile else 'learn_forms_model.pytorch.pth'
traindir = args.traindir if args.traindir else '/nfs/smi/home/smi/MongoDbQueries/Scanned_Forms/img/training'
testdir  = args.valdir   if args.valdir   else '/nfs/smi/home/smi/MongoDbQueries/Scanned_Forms/img/validation'


# ----------------------------------------------------------------------
# PyTorch mechanisms

# Image transformations
train_transforms = transforms.Compose([transforms.Resize((224,224)),
                                       transforms.ToTensor(),                                
                                       torchvision.transforms.Normalize(
                                           mean=[0.485, 0.456, 0.406],
                                           std=[0.229, 0.224, 0.225],),
                                       ])
test_transforms = transforms.Compose([transforms.Resize((224,224)),
                                      transforms.ToTensor(),
                                      torchvision.transforms.Normalize(
                                          mean=[0.485, 0.456, 0.406],
                                          std=[0.229, 0.224, 0.225],),
                                      ])

# Datasets
train_data = datasets.ImageFolder(traindir, transform=train_transforms)
test_data = datasets.ImageFolder(testdir, transform=test_transforms)

# Dataloaders
trainloader = torch.utils.data.DataLoader(train_data, shuffle = True, batch_size=16)
testloader = torch.utils.data.DataLoader(test_data, shuffle = True, batch_size=16)

# ----------------------------------------------------------------------
# Define the neural network model

# Create a training function
def make_train_step(model, optimizer, loss_fn):
    """ Returns a training step function that, given (x,y) returns loss.
    The function will use the given model, optimizer and loss function.
    """
    def train_step(x,y):
        # Make prediction
        yhat = model(x)
        # Enter train mode
        model.train()
        # Compute loss
        loss = loss_fn(yhat,y)
        loss.backward()
        optimizer.step()
        optimizer.zero_grad()
        #optimizer.cleargrads()
        return loss
    return train_step

# Don’t write a network from scratch, adapt a pre-trained model by adding a head composed of other dense layers.
# The last dense layer will be composed of a single neuron that will use a sigmoid activation function so that we will have an output probability of being 0 or 1.
# Must be careful not to train the base model that has already been previously trained.
# Download a pretrained model (resnet) and freeze all the parameters.
# Then change the last linear layer in order to customize the model to become a binary classifier.

from torchvision import datasets, models, transforms
import torch.nn as nn

device = "cuda" if torch.cuda.is_available() else "cpu"
print("Running on %s" % device)
#model = models.resnet18(pretrained=True) # deprecated, use:
model = models.resnet18(weights=models.ResNet18_Weights.DEFAULT)

# Freeze all params in original model
for params in model.parameters():
  params.requires_grad_ = False

# Add a new final layer
nr_filters = model.fc.in_features  # Number of input features of last layer
model.fc = nn.Linear(nr_filters, 1)

model = model.to(device)

# ----------------------------------------------------------------------
# Define loss, optimizer and train_step

from torch.nn.modules.loss import BCEWithLogitsLoss
from torch.optim import lr_scheduler

# Loss
loss_fn = BCEWithLogitsLoss() #binary cross entropy with sigmoid, so no need to use sigmoid in the model

# Optimizer
optimizer = torch.optim.Adam(model.fc.parameters()) 
print('Optimizer = %s' % optimizer)

# Training step
train_step = make_train_step(model, optimizer, loss_fn)
print('Train step = %s' % train_step)


# ----------------------------------------------------------------------
# Train the model

from tqdm import tqdm

losses = []
val_losses = []
epoch_train_losses = []
epoch_test_losses = []
early_stopping_tolerance = 3
early_stopping_threshold = 0.03

for epoch in range(n_epochs):
    epoch_loss = 0
    print('Starting epoch %s' % epoch)
    for i ,data in tqdm(enumerate(trainloader), total = len(trainloader)): # Iterate over batches
        x_batch , y_batch = data
        x_batch = x_batch.to(device) #move to gpu
        y_batch = y_batch.unsqueeze(1).float() # Convert target to same nn output shape
        y_batch = y_batch.to(device) #move to gpu

        loss = train_step(x_batch, y_batch)
        epoch_loss += loss/len(trainloader)
        losses.append(loss)
    
    epoch_train_losses.append(epoch_loss)
    print('\nEpoch : {}, train loss : {}'.format(epoch+1,epoch_loss))

    # Validation doesnt require gradient
    with torch.no_grad():
        cum_loss = 0
        for x_batch, y_batch in testloader:
            x_batch = x_batch.to(device)
            y_batch = y_batch.unsqueeze(1).float() # Convert target to same nn output shape
            y_batch = y_batch.to(device)

            # Model to eval mode
            model.eval()

            yhat = model(x_batch)
            val_loss = loss_fn(yhat,y_batch)
            cum_loss += loss/len(testloader)
            val_losses.append(val_loss.item())

        epoch_test_losses.append(cum_loss)
        print('Epoch : {}, val loss : {}'.format(epoch+1,cum_loss))  
    
        best_loss = min(epoch_test_losses)
    
        # Save best model
        if cum_loss <= best_loss:
            print('keeping this model as loss %f < %f' % (cum_loss, best_loss))
            best_model_wts = model.state_dict()
    
        # Early stopping
        early_stopping_counter = 0
        if cum_loss > best_loss:
            early_stopping_counter +=1

        if (early_stopping_counter == early_stopping_tolerance):
            print("\nTerminating: early stopping, reached %d good losses" % early_stopping_counter)
            break
        if (best_loss <= early_stopping_threshold):
            print("\nTerminating: early stopping, reached a loss %f < %f" % (best_loss, early_stopping_threshold))
            break


# ----------------------------------------------------------------------
# Load an existing model, if no epochs were required, or save the trained model

if n_epochs > 0:
    # Load best model
    model.load_state_dict(best_model_wts)
    print('Saving model to %s' % model_file)
    torch.save(model.state_dict(), model_file)
else:
    print('Loading model from %s' % model_file)
    model.load_state_dict(torch.load(model_file))
    model.to(device)


# ----------------------------------------------------------------------
# Inference

import matplotlib.pyplot as plt 

def inference(test_data):
  idx = torch.randint(1, len(test_data), (1,))
  sample = torch.unsqueeze(test_data[idx][0], dim=0).to(device)
  print('inference on sample %d of %d' % (idx, len(test_data)))

  # calculate probability from tensor
  prob = torch.sigmoid(model(sample))
  if prob < 0.5:
    print("Prediction : Cat (%f)" % prob)
  else:
    print("Prediction : Dog (%f)" % prob)

  print('showing image %d' % idx)
  plt.imshow(test_data[idx][0].permute(1, 2, 0))
  plt.show()

#inference(test_data)
#inference(test_data)
#inference(test_data)
#inference(test_data)
#inference(test_data)

# ----------------------------------------------------------------------
# Check how the network performs on the whole dataset:

import numpy as np
correct = 0
total = 0
# since we're not training, we don't need to calculate the gradients for our outputs
with torch.no_grad():
    for data in testloader:
        images, labels = data
        # Show as image:
        #img = images[0].cpu().numpy()
        ## transpose image to fit plt input
        #img = img.T
        # Normalise image
        #data_min = np.min(img, axis=(1,2), keepdims=True)
        #data_max = np.max(img, axis=(1,2), keepdims=True)
        #scaled_data = (img - data_min) / (data_max - data_min)
        # Show image
        #plt.imshow(scaled_data)
        #plt.show()
        # Convert into device space
        images = images.to(device)
        labels = labels.to(device)
        # calculate outputs by running images through the network
        outputs = model(images)
        # Calculate how many correct
        for idx, xx in enumerate(torch.sigmoid(outputs)):
          vv = 0 if xx < 0.5 else 1
          if vv == labels[idx]:
            correct += 1
        total += labels.size(0)
        #correct += (predicted == labels).sum().item()
print(f'Accuracy of the network on the test images: {100 * correct // total} % ({correct} out of {total})')
