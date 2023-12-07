# Classes and functions for managing DICOM images in PyTorch

# Class ScannedFormDetector is a simple binary classification class
# so not actually specific to scanned forms. It can be trained given
# a list of filenames, which can be DICOM files not just images, and
# it can run inference to classify a list of filenames.

# Class DicomDataset is a replacement for the pytorch ImageFolder class.
# Instead of requiring a specific directory structure this one can take
# a list of filenames.

import csv
import logging
import random
from tqdm import tqdm
from PIL import Image
from DicomPixelAnon.dicomimage import DicomImage
import torch, torchvision
from torchvision import datasets, models, transforms
from torch.nn.modules.loss import BCEWithLogitsLoss
from torch.optim import lr_scheduler

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------

class DicomDataset(torch.utils.data.Dataset):
    """ Read a CSV file of class,filename.
    If you want the same CSV to serve as both training and testing then
    pass it with a percentage e.g. 80 or 20 and random rows will be selected.
    Secret option: if you set is_dicom then the csv_file is actually just a
    single DICOM filename, and given a class of 0, which is only useful for
    inference not training of course.
    Normally a dataset returns a tuple of (list_of_img, list_of_classes)
    but if you pass return_path=True then the image pathname is also returned.
    If you pass check_valid=True then it checks all filenames are valid
    image/DICOM files so you get pre-warning about invalid ones before
    running the slow training process.
    """

    def __valid_dicom(self, filename):
        try:
            ds = DicomImage(filename)
            return True
        except:
            logger.warn('not a valid DICOM: %s' % filename)
            return False


    def __init__(self, filename, root_dir = None, transform = None, percent = 100, is_dicom = False, return_path = False, check_valid = False):
        self.debug = False
        self.root_dir = root_dir
        self.transform = transform
        self.return_path = return_path
        self.file_list = list() # list of {class,filename}
        # percent can be 0..1 or 0..100 so normalise to 0..1
        if percent > 1:
            percent = percent / 100.0
        # If a single filename or a list of filenames
        if is_dicom:
            if isinstance(filename, list):
                for file in filename:
                    # Randomly select from list
                    # A single filename is added as class=0
                    if (random.random() < percent) and (not check_valid or self.__valid_dicom(file)):
                        self.file_list.append( { 'class':0, 'filename': file } )
            else:
                # A single filename is added as class=0
                self.file_list.append( { 'class':0, 'filename': filename } )
            return
        # If a CSV filename
        with open(filename) as fd:
            rdr = csv.DictReader(fd)
            for row in rdr:
                # Randomly select from rows
                if (random.random() < percent) and (not check_valid or self.__valid_dicom(row['filename'])):
                    self.file_list.append(row)
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
        # Read input file
        try:
            # Read as DICOM file
            item_dicom = DicomImage(item_path)
            img = item_dicom.image(frame = 0).convert('RGB')
            if self.debug: print('LOAD %s = %s' % (item_class, item_path))
        except Exception as e:
            # Read as image file
            try:
                img = Image.open(item_path).convert('RGB')
            except Exception as e:
                logger.error("ERROR: Cannot read as DICOM or Image: %s" % item_path)
                raise e                
        # Extract greyscale image from the first frame, then convert to RGB
        if self.debug: img.save(os.path.basename(item_path) + '.orig.png')
        # Convert to tensor
        if self.transform:
            img = self.transform(img)
        if self.debug: torchvision.transforms.ToPILImage()(img).save(os.path.basename(item_path) + '.torch.png')
        if self.return_path:
            return (img, item_class, item_path)
        return (img, item_class)


# ---------------------------------------------------------------------

class ScannedFormDetector:
    """ A simple binary classifier which can train from a list of image
    files or DICOM files and which can classify (infer) from a list.
    Instantiate it for training with a save_model_path or for
    inference with a load_model_path. Then call train_* or test_* with
    either a list of files (images or DICOMs) or a CSV file that contains
    two columns 'class' and 'filename'. Class should be 0 or 1. Filename
    can be relative to a specified root_dir if necessary (e.g. PACS_ROOT).
    """

    # Class variable for transforming RGB image into tensor
    rgb_transforms = transforms.Compose([
        transforms.Resize((224,224)),
        transforms.ToTensor(),
        torchvision.transforms.Normalize(
            mean=[0.485, 0.456, 0.406],
            std=[0.229, 0.224, 0.225],),
    ])

    def __init__(self, load_model_path = None, save_model_path = None):
        # Determine static variables within this class instance
        self.debug = False
        self.shuffle = True
        self.batch_size = 16
        self.load_model_path = load_model_path
        self.save_model_path = save_model_path
        # To be available externally after a successful run:
        self.training_loss = 999
        self.infer_accuracy = 0
        self.infer_num_correct = 0
        self.infer_num_total = 0

        # Determine GPU device
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device_loc = torch.device(self.device)

        # If debugging you might want deterministic behaviour
        if self.debug:
            torch.manual_seed(0)
            torch.backends.cudnn.benchmark = False
            torch.use_deterministic_algorithms(True)
            self.shuffle = False

        # Create the model
        self.model = models.resnet18(weights=models.ResNet18_Weights.DEFAULT)
        # Freeze all params in original model
        for params in self.model.parameters():
            params.requires_grad_ = False
        # Add a new final layer
        nr_filters = self.model.fc.in_features  # Number of input features of last layer
        self.model.fc = torch.nn.Linear(nr_filters, 1)

        # Load model parameters from training
        if load_model_path:
            self.model.load_state_dict(torch.load(self.load_model_path, map_location=self.device_loc))
            self.model.eval()

        self.model.to(self.device)
        return


    def __show_img(img):
        """ Display a window showing the given pytorch image tensor
        """
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


    def __train(self, n_epochs = 20):
        """ Train a new model.
        Don’t write a network from scratch, adapt a pre-trained model by adding a head composed of other dense layers.
        The last dense layer will be composed of a single neuron that will use a sigmoid activation function so that we will have an output probability of being 0 or 1.
        Must be careful not to train the base model that has already been previously trained.
        Download a pretrained model (resnet) and freeze all the parameters.
        Then change the last linear layer in order to customize the model to become a binary classifier.
        Returns the best loss value.
        """
        # Create a training function
        def make_train_step(model, optimizer, loss_fn):
            """ Returns a training step function that, given (x,y) returns loss.
            The function will use the given model, optimizer and loss function.
            """
            def train_step(x,y):
                # Make prediction
                yhat = self.model(x)
                # Enter train mode
                self.model.train()
                # Compute loss
                loss = loss_fn(yhat,y)
                loss.backward()
                optimizer.step()
                optimizer.zero_grad()
                #optimizer.cleargrads()
                return loss
            # Return the new function
            return train_step

        # Define loss, optimizer and train_step
        loss_fn = BCEWithLogitsLoss() # binary cross entropy with sigmoid, so no need to use sigmoid in the model
        optimizer = torch.optim.Adam(self.model.fc.parameters()) 
        train_step = make_train_step(self.model, optimizer, loss_fn)

        losses = []
        val_losses = []
        epoch_train_losses = []
        epoch_test_losses = []
        early_stopping_tolerance = 3
        early_stopping_threshold = 0.03

        for epoch in range(n_epochs):
            epoch_loss = 0
            print('Starting epoch %s / %s' % (epoch, n_epochs))

            # Training
            # Iterate over batches
            for idx, data in tqdm(enumerate(self.train_loader), total = len(self.train_loader)):
                x_batch , y_batch, paths = data
                x_batch = x_batch.to(self.device) # move to gpu
                y_batch = y_batch.unsqueeze(1).float() # Convert target to same nn output shape
                y_batch = y_batch.to(self.device) # move to gpu

                loss = train_step(x_batch, y_batch)
                epoch_loss += loss/len(self.train_loader)
                losses.append(loss)
            epoch_train_losses.append(epoch_loss)
            print('\nEpoch : {}, train loss : {}'.format(epoch+1,epoch_loss))

            # Validation (doesn't require gradient)
            with torch.no_grad():
                cum_loss = 0
                for x_batch, y_batch, paths in self.loader:
                    x_batch = x_batch.to(self.device)
                    y_batch = y_batch.unsqueeze(1).float() # Convert target to same nn output shape
                    y_batch = y_batch.to(self.device)

                    # Model to eval mode
                    self.model.eval()

                    yhat = self.model(x_batch)
                    val_loss = loss_fn(yhat,y_batch)
                    cum_loss += loss/len(self.loader)
                    val_losses.append(val_loss.item())

                prev_best_loss = min(epoch_test_losses + [999])
                epoch_test_losses.append(cum_loss)
                best_loss = min(epoch_test_losses)
                print('Epoch : {}, val loss : {}'.format(epoch+1, cum_loss))  

                # Save best model
                if cum_loss <= best_loss:
                    print(' Keeping this model as loss %f < %f' % (cum_loss, prev_best_loss))
                    best_model_wts = self.model.state_dict()

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

        # Load best model and save to file
        self.model.load_state_dict(best_model_wts)
        print('Saving model to %s' % self.save_model_path)
        torch.save(self.model.state_dict(), self.save_model_path)
        self.model.to(self.device)
        self.training_loss = best_loss
        return best_loss


    # -----------------------------------------------------------------
    def __infer(self):
        """ Run inference on the model using the images which have been
        loaded into self.loader by test_image_list() or test_csv_file().
        Returns a list of { class, orig_class, sigmoid, filename } dicts.
        You can decide if sigmoid is too close to 0.5 that result has
        less confidence that if it's very close to 0 or 1.
        """
        correct = 0
        total = 0
        return_list = []
        # since we're not training, we don't need to calculate the gradients for our outputs
        with torch.no_grad():
            for data in self.loader:
                # Get images and labels, and image path if return_path was True
                images, labels, item_path = data
                # Convert into device space
                images = images.to(self.device)
                labels = labels.to(self.device)
                # calculate outputs by running images through the network
                outputs = self.model(images)
                # Calculate how many correct
                for idx, sigm in enumerate(torch.sigmoid(outputs)):
                  orig_class = int(labels[idx])
                  pred_class = 0 if float(sigm) < 0.5 else 1
                  if self.debug: print('idx %s label should be %s got sigm %s (%s)' % (idx,labels[idx],sigm,item_path[idx]))
                  return_list.append( {
                    'filename': item_path[idx],
                    'class': pred_class,
                    'class_orig': orig_class,
                    'sigmoid': float(sigm)
                  } )
                  if pred_class == orig_class:
                    correct += 1
                  if self.debug: print('predicted class %s for %s' % (pred_class, item_path[idx]))
                  #if self.debug: __show_img(images[idx])
                total += labels.size(0)
        self.infer_accuracy = 100 * correct // total
        self.infer_num_correct = correct
        self.infer_num_total = total
        if self.debug: print(f'Accuracy of the network on the test images: {self.infer_accuracy} % ({correct} out of {total})')
        return return_list


    def train_csv_file(self, train_csv_file, test_csv_file = None, root_dir = None, n_epochs = 20):
        if not test_csv_file:
            test_csv_file = train_csv_file
        split_csv_for_testing = (train_csv_file == test_csv_file)
        percent_train = 80 if split_csv_for_testing else 100
        percent_test  = 20 if split_csv_for_testing else 100
        train_data = DicomDataset(train_csv_file, root_dir = root_dir, return_path = True,
            transform = ScannedFormDetector.rgb_transforms,
            percent = percent_train)
        test_data = DicomDataset(test_csv_file, root_dir = root_dir, return_path = True,
            transform = ScannedFormDetector.rgb_transforms, 
            percent = percent_test)
        self.train_loader = torch.utils.data.DataLoader(train_data, shuffle = self.shuffle, batch_size = self.batch_size)
        self.loader = torch.utils.data.DataLoader(test_data, shuffle = self.shuffle, batch_size = self.batch_size)
        training_loss = self.__train(n_epochs)
        result_list = self.__infer()
        print('Training loss %s, accuracy on test images %s' % (self.training_loss, self.infer_accuracy))
        return self.infer_accuracy


    def test_image_list(self, img_list, root_dir = None):
        """ Define a list of images which can be used for training or inference.
        The filenames can be absolute or relative to root_dir.
        Files can be DICOM image files, or normal images (PNG/JPEG).
        """
        test_data = DicomDataset(img_list, root_dir = root_dir, transform = ScannedFormDetector.rgb_transforms, return_path = True, is_dicom = True)
        self.loader = torch.utils.data.DataLoader(test_data, shuffle = self.shuffle, batch_size = self.batch_size)
        return self.__infer()


    def test_csv_file(self, csv_file, root_dir = None):
        """ Define a list of images which can be used for training or inference.
        The CSV file must have a 'filename' column, filenames can be absolute or
        relative to root_dir, and can be DICOM or normal PNG/JPEG image.
        For training a 'class' column is required, values 0 or 1.
        """
        test_data = DicomDataset(csv_file, root_dir = root_dir, transform = ScannedFormDetector.rgb_transforms, return_path = True)
        self.loader = torch.utils.data.DataLoader(test_data, shuffle = self.shuffle, batch_size = self.batch_size)
        return self.__infer()
