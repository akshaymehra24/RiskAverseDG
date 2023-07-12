
import warnings
warnings.simplefilter(action='ignore', category=FutureWarning)
import numpy as np
import tensorflow as tf
import torch
from torchvision import transforms
from torchvision.datasets import ImageFolder
from torch.utils.data import DataLoader
import os

tf.keras.backend.set_floatx('float32')
ce_loss_none = tf.keras.losses.CategoricalCrossentropy(from_logits=True, reduction=tf.keras.losses.Reduction.NONE)

HEIGHT = 224
WIDTH = 224
NCH = 3

def load_VLCS_sources(sources, BATCH_SIZE, val_split=True):
    
    root = "path_to_VLCS"

    environments = [f.name for f in os.scandir(root) if f.is_dir()]
    environments = sorted(environments)
    
    augment_transform = transforms.Compose([
        transforms.RandomResizedCrop(224, scale=(0.8, 1.0)),
        transforms.RandomHorizontalFlip(0.5),
        transforms.ColorJitter(0.4, 0.4, 0.4, 0.4),
        transforms.RandomGrayscale(0.1),
        transforms.ToTensor(),
    ])
    
    common_transform = transforms.Compose([
        transforms.Resize((224,224)),
        transforms.ToTensor(),
    ])
    
    src_data_loaders = []
    val_data = []
    val_labels = []
    
    for i, environment in enumerate(environments):
    
        if i in sources:
            print("source:", environment)
            if val_split:
                
                val_path = os.path.join(root, environment+"/crossval")
                val_env_dataset = ImageFolder(val_path, transform=common_transform)
                
                train_path = os.path.join(root, environment+"/train")
                train_env_dataset = ImageFolder(train_path, transform=augment_transform)
                
            else:
                train_path = os.path.join(root, environment+"/full")
                train_env_dataset = ImageFolder(train_path, transform=augment_transform)
            
            train_loader = DataLoader(train_env_dataset, batch_size=BATCH_SIZE, shuffle=True)
            src_data_loaders.append(train_loader)
            
            if val_split:
                val_loader = DataLoader(val_env_dataset, len(val_env_dataset))
                val_data_array = next(iter(val_loader))[0].permute(0, 2, 3, 1).numpy()
                val_labels_array = next(iter(val_loader))[1].numpy()
                
                val_data.append(val_data_array)
                val_labels.append(val_labels_array)
    
        
    return src_data_loaders, val_data, val_labels
    
def load_VLCS_targets(targets):
    
    root = "path_to_VLCS"

    environments = [f.name for f in os.scandir(root) if f.is_dir()]
    environments = sorted(environments)
    
    common_transform = transforms.Compose([
        transforms.Resize((224,224)),
        transforms.ToTensor(),
    ])
    
    target_data = []
    target_labels = []

    for i, environment in enumerate(environments):
    
        if i in targets:
            path_1 = os.path.join(root, environment+"/test")
            path_2 = os.path.join(root, environment+"/full")
            
            env_dataset_1 = ImageFolder(path_1, transform=common_transform)
            env_dataset_2 = ImageFolder(path_2, transform=common_transform)
            
            image_datasets = torch.utils.data.ConcatDataset([env_dataset_1, env_dataset_2])
            
            loader = DataLoader(image_datasets, len(image_datasets))
            dataset_array = next(iter(loader))[0].permute(0, 2, 3, 1).numpy()
            dataset_labels_array = next(iter(loader))[1].numpy()
            
            target_data.append(dataset_array)
            target_labels.append(dataset_labels_array)

    return target_data, target_labels


def eval_accuracy(x_test, y_test, base_model, classifier):
    correct = 0
    points = 0
    loss = 0
    batch_size = 50
    nb_batches = int(len(x_test)/batch_size)
    if len(x_test)%batch_size!= 0:
        nb_batches += 1
    
    for batch in range(nb_batches):
        ind_batch = range(batch_size*batch, min(batch_size*(1+batch), len(x_test)))
        rep = base_model(x_test[ind_batch], training=False)
        pred = classifier(rep, training=False)
        
        correct += np.sum(np.argmax(pred,1) == np.argmax(y_test[ind_batch],1))
        points += len(ind_batch)
        loss += np.sum(ce_loss_none(y_test[ind_batch], pred).numpy())
    
    return (correct / np.float32(points))*100., loss/ np.float32(points)

def mini_batch_class_balanced(label, sample_size=20):
    ''' sample the mini-batch with class balanced
    '''
    label = np.argmax(label, axis=1)

    n_class = len(np.unique(label))
    index = []
    for i in range(n_class):
        
        s_index = np.argwhere(label==i).flatten()
        np.random.shuffle(s_index)
        print(i, len(s_index[:sample_size]))
        index.append(s_index[:sample_size])

    index = [item for sublist in index for item in sublist]
    index = np.array(index, dtype=int)
    return index


def restore_original_image_from_array_vgg(x, data_format='channels_last'):
    mean = [103.939, 116.779, 123.68]

    # Zero-center by mean pixel
    if data_format == 'channels_first':
        if x.ndim == 3:
            x[0, :, :] += mean[0]
            x[1, :, :] += mean[1]
            x[2, :, :] += mean[2]
        else:
            x[:, 0, :, :] += mean[0]
            x[:, 1, :, :] += mean[1]
            x[:, 2, :, :] += mean[2]
    else:
        x[..., 0] += mean[0]
        x[..., 1] += mean[1]
        x[..., 2] += mean[2]

    if data_format == 'channels_first':
        # 'BGR'->'RGB'
        if x.ndim == 3:
            x = x[::-1, ...]
        else:
            x = x[:, ::-1, ...]
    else:
        # 'BGR'->'RGB'
        x = x[..., ::-1]

    return np.array(np.clip(x/255., 0, 1))
