# learn_forms.py

Detect scanned forms vs clinical images.

Basically just a binary classification problem.

Use the shell script to create a suitable directory structure
then run the python script to train a model, then you can run
inference by omitting the training step.

## Usage

For training the directory structure should be two directories,
TRAINDIR and VALDIR, and inside both there should be directories
for each class (two directories for binary classification).

Test the model by running with `--epochs 0` to prevent training.

Specify a model file to load when testing, or to save when training.


```
usage: learn_forms.py [-d] [-e EPOCHS] [-m MODELFILE] [-t TRAINDIR] [-v VALDIR]


options:
  -e EPOCHS, --epochs EPOCHS
                        number of epoch runs during training
  -m MODELFILE, --model MODELFILE
                        filename to load/save trained model
  -t TRAINDIR, --traindir TRAINDIR
                        directory of training images
  -v VALDIR, --valdir VALDIR
                        directory of validation images
```
