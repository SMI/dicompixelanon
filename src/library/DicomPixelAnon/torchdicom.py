# Class and functions for managing DICOM images in PyTorch

import csv
import logging
import random
import torch, torchvision
from torchvision import datasets, models, transforms
from PIL import Image
from DicomPixelAnon.dicomimage import DicomImage

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
    """

    def __init__(self, filename, root_dir = None, transform = None, percent = 100, is_dicom = False, return_path = False):
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
                    if random.random() < percent:
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
                if random.random() < percent:
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
    """
    """

    # Class variable for transforming RGB image into tensor
    rgb_transforms = transforms.Compose([
        transforms.Resize((224,224)),
        transforms.ToTensor(),
        torchvision.transforms.Normalize(
            mean=[0.485, 0.456, 0.406],
            std=[0.229, 0.224, 0.225],),
    ])

    def __init__(self, model_path = 'learn_forms_model.pytorch.pth'):
        # Determine static variables within this class instance
        self.debug = False
        self.shuffle = False
        self.batch_size = 16

        # Determine GPU device
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        device_loc = torch.device(self.device)

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
        self.model.load_state_dict(torch.load(model_path, map_location=device_loc))
        self.model.eval()
        self.model.to(self.device)
        return

    def show_img(img):
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

    def infer(self):
        """ Run inference on the model using the images which have been
        loaded into self.loader by test_image_list() or test_csv_file().
        Returns a list of { class, filename } dicts.
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
                  if self.debug: print('idx %s label should be %s got sigm %s (%s)' % (idx,labels[idx],sigm,item_path[idx]))
                  vv = 0 if sigm < 0.5 else 1
                  return_list.append( { 'class':vv, 'filename':item_path[idx] } )
                  if vv == labels[idx]:
                    correct += 1
                  if self.debug: print('predicted class %s for %s' % (vv, item_path[idx]))
                  #if self.debug: show_img(images[idx])
                total += labels.size(0)
        if self.debug: print(f'Accuracy of the network on the test images: {100 * correct // total} % ({correct} out of {total})')
        return return_list


    def test_image_list(self, img_list, root_dir = None):
        """ Define a list of images which can be used for training or inference.
        The filenames can be absolute or relative to root_dir.
        Files can be DICOM image files, or normal images (PNG/JPEG).
        """
        test_data = DicomDataset(img_list, root_dir = root_dir, transform = ScannedFormDetector.rgb_transforms, return_path = True, is_dicom = True)
        self.loader = torch.utils.data.DataLoader(test_data, shuffle = self.shuffle, batch_size = self.batch_size)
        return self.infer()


    def test_csv_file(self, csv_file, root_dir = None):
        """ Define a list of images which can be used for training or inference.
        The CSV file must have a 'filename' column, filenames can be absolute or
        relative to root_dir, and can be DICOM or normal PNG/JPEG image.
        For training a 'class' column is required, values 0 or 1.
        """
        test_data = DicomDataset(csv_file, root_dir = root_dir, transform = ScannedFormDetector.rgb_transforms, return_path = True)
        self.loader = torch.utils.data.DataLoader(test_data, shuffle = self.shuffle, batch_size = self.batch_size)
        return self.infer()
