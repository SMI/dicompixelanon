# learn_forms.py

Detect scanned forms vs clinical images.

This is basically just a binary classification problem.
Ideally it would be a unary classification (OCC) since the image is
either a form or something (anything) else. Unary classification is
less well supported in general so we will stick with binary.

The normal approach to training the model is to create a directory
structure with 'training' and 'validation' directories, both having
two subdirectories of images, one for each class (form or clinical).
Use the shell script to create a suitable directory structure
then run the python script to train a model, then you can run
inference by omitting the training step.

The new approach uses a CSV file listing all the filenames with their
class. Column headers are 'class' of integers 0,1 and 'filename'.
Filenames can be absolute, or relative to a specified root directory.

Internally the DICOM images are converted to greyscale and enhanced
in the same way as done for OCR and dcmaudit, then converted to RGB
because the ML model is best used with RGB images.

## Requirements

Requirements: tqdm, torch, torchvision, PIL, maybe matplotlib
Remember to specifically download the CPU version of PyTorch if
you don't have a GPU.

You will need ResNet from https://download.pytorch.org/models/resnet18-f37072fd.pth
in `~/.cache/torch/hub/checkpoints/resnet18-f37072fd.pth`
It will be downloaded automatically if not already present,
or set `TORCH_HOME` to the directory which contains `hub/...`.

## Usage

If using a CSV file the prepare two files, one with filenames for
training and one with filenames for validation. Or use the same
filename for both and it will randomly pick 80% of them for training
and leave 20% for validation.

If not using CSV files then the directory structure should be two directories,
TRAINDIR and VALDIR, and inside both there should be directories
for each class (two directories for binary classification).

Test the model by running with `--epochs 0` to prevent training;
this will run the model through the validation images.
Use -i to perform inference on your own images.

Specify a model file to load when testing, or to save when training.


```
usage: learn_forms.py [-h] [-d] [-e EPOCHS] [-m MODELFILE] [-r ROOTDIR] [-t TRAINCSV] [-v VALCSV]

options:
  -e EPOCHS, --epochs EPOCHS
                        number of epoch runs during training, or 0 to run only testing inference
  -m MODELFILE, --model MODELFILE
                        filename to load/save trained model
  -r ROOTDIR, --rootdir ROOTDIR
                        directory prefix for images
  -t TRAINCSV, --traincsv TRAINCSV
                        CSV of training images
  -v VALCSV, --valcsv VALCSV
                        CSV of validation images, can be same as traincsv for auto 80/20 split
```

## Results


In `$SMI_ROOT/MongoDbQueries/Scanned_Forms/2023-12-00` see `README.txt`.

Create `scanned_forms.txt` as a set of filenames that contain scanned forms
manually curated.

Create `clinical.txt` as a set of filenames that contain clinical images but make sure no forms. Use `collect_clinical.sh` to run `random_combinations` on the `filepos` extractions.

Create `input_classes.csv` containing columns `class,filename` being a concatenation of `clinical.txt` with a class of 0 and `scanned_forms.txt` with a class of 1.

Run `learn_forms.py -d -m learn_forms_model.pytorch.pth -t input_classes.csv -v input_classes.csv`

Output:
```
Epoch 4 train loss 0.05108
Epoch 4 val loss 0.017233
Terminating as loss < 0.03
Accuracy of the network on the test images = 98% (433 out of 440)
```

Run `test_forms.py` to do an independent test (no training).
Use the `-v` option to pass a CSV file as above,
or the `-i` option for image/DICOM filenames.

# References

Binary image classification:
https://towardsdatascience.com/binary-image-classification-in-pytorch-5adf64f8c781
uses dataset https://www.kaggle.com/datasets/biaiscience/dogs-vs-cats

Alternatively, training for 10 classes with RGB images from CIFAR
https://pytorch.org/tutorials/beginner/blitz/cifar10_tutorial.html
which references this (1-channel mono images):
https://pytorch.org/tutorials/recipes/recipes/defining_a_neural_network.html
