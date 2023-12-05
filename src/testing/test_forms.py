#!/usr/bin/env python3

# Requirements:
#  tqdm, torch, torchvision [matplotlib]
# You will need "https://download.pytorch.org/models/resnet18-f37072fd.pth"
# in "/home/arb/.cache/torch/hub/checkpoints/resnet18-f37072fd.pth"
# (it will be downloaded automatically if not already present).

# Usage:
#  create a CSV file containing two columns, class (integer) and filename
#  The filenames can be relative as a root_dir may be specified.
#  There should only be two classes 0 and 1 (but you can use more?)
#  All files should be DICOM, only first frame is used, it is converted
#  to greyscale when loaded (although training is done using a model
#  trained on RGB so greyscale is converted to RGB internally).

# References:
# Binary image classification:
#  https://towardsdatascience.com/binary-image-classification-in-pytorch-5adf64f8c781
# Uses dataset https://www.kaggle.com/datasets/biaiscience/dogs-vs-cats

# Alternatively, training for 10 classes with RGB images from CIFAR
#  https://pytorch.org/tutorials/beginner/blitz/cifar10_tutorial.html
# which references this (1-channel mono images):
#  https://pytorch.org/tutorials/recipes/recipes/defining_a_neural_network.html

import argparse
import csv
import logging
import os
import random
import sys
import torch
import torchvision
from torchvision import datasets, models, transforms
from DicomPixelAnon.dicomimage import DicomImage
from PIL import Image

logger = logging.getLogger(__name__)

# Command line parameters
parser = argparse.ArgumentParser(description='Detect scanned forms vs clinical images')
parser.add_argument('-d', '--debug', action="store_true", default=False, help='debug')
parser.add_argument('-m', '--model', dest='modelfile', action="store", default='learn_forms_model.pytorch.pth', help='filename to load/save trained model')
parser.add_argument('-r', '--rootdir', dest='rootdir', action="store", help='directory prefix for images')
parser.add_argument('-v', '--valcsv', dest='valcsv', action="store", help='CSV of validation images')
parser.add_argument('-i', '--image', dest='image', action="store", nargs='*', help='image to test (an image file or a DICOM file)')
args = parser.parse_args()
model_file = args.modelfile

# Original model was trained on RGB images so we should fine-tune/test it using RGB
load_as_rgb = True

# ---------------------------------------------------------------------
# For deterministic behaviour

#torch.manual_seed(0)
#torch.backends.cudnn.benchmark = False
#torch.use_deterministic_algorithms(True)

# ---------------------------------------------------------------------
# Image transformations

test_transforms = transforms.Compose([transforms.Resize((224,224)),
                                      transforms.ToTensor(),
                                      torchvision.transforms.Normalize(
                                          mean=[0.485, 0.456, 0.406],
                                          std=[0.229, 0.224, 0.225],),
                                      ])

# ---------------------------------------------------------------------
# Class for loading DICOM images from a set of filenames in a CSV file.

class DicomDataset(torch.utils.data.Dataset):
    """ Read a CSV file of class,filename.
    If you want the same CSV to serve as both training and testing then
    pass it with a percentage e.g. 80 or 20 and random rows will be selected.
    Secret option: if you set is_dicom then the csv_file is actually just a
    single DICOM filename, and given a class of 0, which is only useful for
    inference not training of course.
    Normally a dataset returns a tuple of (list_of_img, list_of_classes)
    but if you pass return_path=True then the image pathname is also returned.
    """

    def __init__(self, csv_file, root_dir = None, transform = None, percent = 100, is_dicom = False, return_path = False):
        self.root_dir = root_dir
        self.transform = transform
        self.return_path = return_path
        self.file_list = list() # list of {class,filename}
        if percent > 1:
            percent = percent / 100.0
        if is_dicom:
            if isinstance(csv_file, list):
                for file in csv_file:
                    self.file_list.append( { 'class':0, 'filename': file } )
            else:
                self.file_list.append( { 'class':0, 'filename': csv_file } )
            return
        fd = open(csv_file)
        rdr = csv.DictReader(fd)
        for row in rdr:
            if random.random() < percent:
                self.file_list.append(row)
        fd.close()
        if not self.file_list:
            raise Exception('Samping %f percent from %s returned no rows' % (percent*100.0, csv_file))

    def __len__(self):
        return len(self.file_list)

    def __getitem__(self, idx):
        item = self.file_list[idx]
        item_class = int(item['class'])
        item_path = item['filename']
        if self.root_dir:
            item_path = os.path.join(self.root_dir, item_path)
        # Read DICOM file
        try:
            item_dicom = DicomImage(item_path)
            img = item_dicom.image(frame = 0).convert('RGB')
            if args.debug: print('LOAD %s = %s' % (item_class, item_path))
        except Exception as e:
            try:
                img = Image.open(item_path).convert('RGB')
            except Exception as e:
                logger.error("ERROR: Cannot read as DICOM or Image: %s" % item_path)
                raise e                
        # Extract greyscale image from the first frame, then convert to RGB
        if args.debug: img.save(os.path.basename(item_path) + '.orig.png')
        # Convert to tensor
        if self.transform:
            img = self.transform(img)
        if args.debug: torchvision.transforms.ToPILImage()(img).save(os.path.basename(item_path) + '.torch.png')
        if self.return_path:
            return (img, item_class, item_path)
        return (img, item_class)

# ---------------------------------------------------------------------
# Loader for the test data

# Read the CSV file but does not load the DICOM images yet.
if args.image:
    test_data = DicomDataset(args.image, root_dir = args.rootdir, transform = test_transforms, return_path = True, is_dicom = True)
else:
    test_data = DicomDataset(args.valcsv, root_dir = args.rootdir, transform = test_transforms, return_path = True)

# A randomised batch loader
testloader = torch.utils.data.DataLoader(test_data, shuffle = True, batch_size=16)


# ----------------------------------------------------------------------
# Define the neural network model


# Adapt a pre-trained model by adding a head composed of other dense layers.
# The last dense layer will be composed of a single neuron that will use a sigmoid activation function so that we will have an output probability of being 0 or 1.
# Must be careful not to train the base model that has already been previously trained.
# Download a pretrained model (resnet) and freeze all the parameters.
# Then change the last linear layer in order to customize the model to become a binary classifier.


device = "cuda" if torch.cuda.is_available() else "cpu"

model = models.resnet18(weights=models.ResNet18_Weights.DEFAULT)

# Freeze all params in original model
for params in model.parameters():
  params.requires_grad_ = False

# Add a new final layer
nr_filters = model.fc.in_features  # Number of input features of last layer
model.fc = torch.nn.Linear(nr_filters, 1)

# ----------------------------------------------------------------------
# Load an existing model, if no epochs were required, or save the trained model

print('Loading model from %s into %s' % (model_file, device))
model.load_state_dict(torch.load(model_file))
model.eval()
model.to(device)


# ----------------------------------------------------------------------
# Function to show on screen an image which has been transformed

def show_img(img):
    import numpy as np
    import matplotlib.pyplot as plt 
    # Show as image:
    img = img.cpu().numpy()
    ## transpose image to fit plt input
    img = img.T
    # Normalise image
    data_min = np.min(img, axis=(1,2), keepdims=True)
    data_max = np.max(img, axis=(1,2), keepdims=True)
    scaled_data = (img - data_min) / (data_max - data_min)
    # Show image
    plt.imshow(scaled_data)
    plt.show()


# ----------------------------------------------------------------------
# Check how the network performs on an input file(s), or the whole test dataset

correct = 0
total = 0
# since we're not training, we don't need to calculate the gradients for our outputs
with torch.no_grad():
    for data in testloader:
        # Get images and labels, and image path if return_path was True
        images, labels, item_path = data
        # Convert into device space
        images = images.to(device)
        labels = labels.to(device)
        # calculate outputs by running images through the network
        outputs = model(images)
        # Calculate how many correct
        for idx, sigm in enumerate(torch.sigmoid(outputs)):
          if args.debug: print('idx %s label should be %s got sigm %s (%s)' % (idx,labels[idx],sigm,item_path[idx]))
          vv = 0 if sigm < 0.5 else 1
          if vv == labels[idx]:
            correct += 1
          if args.image: print('predicted class %s for %s' % (vv, item_path[idx]))
          if args.debug: show_img(images[idx])
        total += labels.size(0)
if not args.image:
    print(f'Accuracy of the network on the test images: {100 * correct // total} % ({correct} out of {total})')
