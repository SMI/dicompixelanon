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

e.g. training on cats/dogs:
```
./learn_forms.py -e 100 -m ~/src/dogs_vs_cats/model_from_subset -t ~/src/dogs_vs_cats/train_subset -v ~/src/dogs_vs_cats/validate_subset
```

e.g. inference:
```
./learn_forms.py -e 0 -m ~/src/dogs_vs_cats/model_from_subset -t ~/src/dogs_vs_cats/train_subset -v ~/src/dogs_vs_cats/validate_subset -i $(find ~/src/dogs_vs_cats/train -type f | shuf -n 30)
```

## Results

Images in `$SMI_ROOT/MongoDbQueries/Scanned_Forms/img/`

```
...
Epoch : 214, train loss : 0.1429
Epoch : 214, val loss : 0.2859
Epoch : 215, train loss : 0.1333
Epoch : 215, val loss : 0.0188
Terminating: early stopping
Saving model to forms_model_pytorch_500epochs.pth
Accuracy of the network on the test images: 75% (30 out of 40)
```
