# -*- coding: utf-8 -*-
"""
Created on Tue Dec 10 15:13:31 2024

@author: 15385
"""
import random
import numpy as np
import torch
from torch.utils.data import Dataset
import torchvision
import torchvision.transforms as transforms

from utils.randaugment import RandomAugment
from utils.utils_algo import generate_uniform_cv_candidate_labels, generate_noise_labels,generate_uniform_cv_candidate_labels_PiCO

def generate_uniform_cv_candidate_labels_ood(labels, partial_rate=0.1):

    # K = int(np.max(labels) - np.min(labels) + 1) # 10
    K = 8
    n = len(labels) # 50000

    partialY = np.zeros((n, K))
    
    # partialY[np.arange(n), labels] = 1.0
    for i, label in enumerate(labels):
        if label <= 7:
            partialY[i, label] = 1.0
        else:
            random_int = random.randint(0, 7)
            partialY[i, random_int] = 1.0

    transition_matrix = np.eye(K)
    transition_matrix[np.where(~np.eye(transition_matrix.shape[0],dtype=bool))]=partial_rate
    print(transition_matrix)
    '''
    transition_matrix = 
        [[1.  0.5 0.5 0.5 0.5 0.5 0.5 0.5 0.5 0.5]
         [0.5 1.  0.5 0.5 0.5 0.5 0.5 0.5 0.5 0.5]
         [0.5 0.5 1.  0.5 0.5 0.5 0.5 0.5 0.5 0.5]
         [0.5 0.5 0.5 1.  0.5 0.5 0.5 0.5 0.5 0.5]
         [0.5 0.5 0.5 0.5 1.  0.5 0.5 0.5 0.5 0.5]
         [0.5 0.5 0.5 0.5 0.5 1.  0.5 0.5 0.5 0.5]
         [0.5 0.5 0.5 0.5 0.5 0.5 1.  0.5 0.5 0.5]
         [0.5 0.5 0.5 0.5 0.5 0.5 0.5 1.  0.5 0.5]
         [0.5 0.5 0.5 0.5 0.5 0.5 0.5 0.5 1.  0.5]
         [0.5 0.5 0.5 0.5 0.5 0.5 0.5 0.5 0.5 1. ]]
    '''
    random_n = np.random.uniform(0, 1, size=(n, K))

    for j in range(n):  # for each instance
        for jj in range(K): # for each class 
            if jj == labels[j]: # except true class
                continue
            # if random_n[j, jj] < transition_matrix[labels[j], jj]:
            if random_n[j, jj] < partial_rate:
                partialY[j, jj] = 1.0

    return partialY

def generate_noise_labels_ood(labels, partialY, noise_rate=0.0):
    partialY_new = [] # must define partialY_new
    for ii in range(len(labels)):
        label = labels[ii]
        plabel =  partialY[ii]
        noise_flag = (random.uniform(0, 1) <= noise_rate) # whether add noise to label
        if noise_flag:
            ## random choose one idx not in plabel
            houxuan_idx = []
            for ii in range(len(plabel)):
                if plabel[ii] == 0: houxuan_idx.append(ii)
            if len(houxuan_idx) == 0: # all category in partial label
                partialY_new.append(plabel)
                continue
            ## add noise in partial label
            newii = random.randint(0, len(houxuan_idx)-1)
            idx = houxuan_idx[newii]
            if label < 8:
                assert plabel[label] == 1, f'plabel[label] != 1'
                assert plabel[idx]   == 0, f'plabel[idx]   != 0'
                plabel[label] = 0
                plabel[idx] = 1
                partialY_new.append(plabel)
            else:
                partialY_new.append(plabel)
        else:
            partialY_new.append(plabel)
    partialY_new = np.array(partialY_new)
    return partialY_new

def load_cifar10(args):
    #######################################################
    print ('obtain train_loader')
    ## train_loader: (data, labels), only read data (target data: (60000, 32, 32, 3))
    temp_train = torchvision.datasets.CIFAR10(root=args.dataset_root, train=True, download=True)
    data_train, dlabels_train = temp_train.data, temp_train.targets # (50000, 32, 32, 3)
    assert np.min(dlabels_train) == 0, f'min(dlabels) != 0'

    ## train_loader: train_givenY
    dlabels_train = np.array(dlabels_train).astype('int')
    print(dlabels_train)
    num_sample = len(dlabels_train)
    
    # Step 1: Create train_givenY (partial labels)
    
    # to do
    train_givenY = generate_uniform_cv_candidate_labels_ood(dlabels_train, args.partial_rate) ## generate partial dlabels
    
    '''
    # For labels 8 and 9, assign partial labels from the range [0-7]
    for i in range(num_sample):
        if dlabels_train[i] == 8 or dlabels_train[i] == 9:
            # Randomly choose a label from 0-7 for partial labels
            train_givenY[i] = np.random.choice(8, size=1)  # This assigns partial labels from {0, 1, ..., 7}
    '''
    
    print('Average candidate num: ', np.mean(np.sum(train_givenY, axis=1)))
    # bingo_rate = np.sum(train_givenY[np.arange(num_sample), dlabels_train] == 1.0) / num_sample
    # print('Average bingo rate: ', bingo_rate)

    # Step 2: Add noise labels (if applicable)
    if args.noisy_type == 'flip':
        train_givenY = generate_noise_labels_ood(dlabels_train, train_givenY, args.noise_rate)
        # bingo_rate = np.sum(train_givenY[np.arange(num_sample), dlabels_train] == 1.0) / num_sample
        # print('Average noise rate: ', 1 - bingo_rate)
    elif args.noisy_type == 'pico':
        train_givenY = generate_uniform_cv_candidate_labels_PiCO(dlabels_train, args.partial_rate, args.noise_rate)
        print('Average candidate num: ', np.mean(np.sum(train_givenY, axis=1)))
        bingo_rate = np.sum(train_givenY[np.arange(num_sample), dlabels_train] == 1.0) / num_sample
        print('Average bingo rate: ', bingo_rate)
        bingo_rate = np.sum(train_givenY[np.arange(num_sample), dlabels_train] == 1.0) / num_sample
        print('Average noise rate: ', 1 - bingo_rate)
    else:
        assert args.noisy_type in ['flip','pico']
    
    ## train_loader: train_givenY->plabel
    dlabels_train = np.array(dlabels_train).astype('float')
    train_givenY = np.array(train_givenY).astype('float')
    plabels_train = (train_givenY != 0).astype('float')  # Partial labels: 1 for known, 0 for unknown

    partial_matrix_dataset = Augmentention(data_train, plabels_train, dlabels_train, train_flag=True)
    partial_matrix_train_loader = torch.utils.data.DataLoader(
        dataset=partial_matrix_dataset, 
        batch_size=args.batch_size,
        num_workers=args.workers,
        shuffle=True, 
        drop_last=True)
    
    #######################################################
    print ('obtain test_loader')
    temp_test = torchvision.datasets.CIFAR10(root=args.dataset_root, train=False, download=True)
    data_test, dlabels_test = temp_test.data, temp_test.targets # (50000, 32, 32, 3)
    assert np.min(dlabels_test) == 0, f'min(dlabels) != 0'

    ## (data, dlabels) -> test_loader
    test_dataset = Augmentention(data_test, dlabels_test, dlabels_test, train_flag=False)
    test_loader = torch.utils.data.DataLoader(
        dataset=test_dataset, 
        batch_size=args.batch_size,
        num_workers=args.workers,
        shuffle=False)

    return partial_matrix_train_loader, train_givenY, test_loader

class Augmentention(Dataset):
    def __init__(self, images, plabels, dlabels, train_flag=True):
        self.images = images
        self.plabels = plabels
        self.dlabels = dlabels
        self.train_flag = train_flag
        normalize_mean = (0.4914, 0.4822, 0.4465)
        normalize_std  = (0.2470, 0.2435, 0.2616)
        if self.train_flag == True:
            self.weak_transform = transforms.Compose([
                transforms.ToPILImage(),
                transforms.Resize((32, 32)),
                transforms.RandomResizedCrop(size=32, scale=(0.2, 1.)),
                transforms.RandomHorizontalFlip(),
                transforms.RandomApply([transforms.ColorJitter(0.4, 0.4, 0.4, 0.1)], p=0.8),
                transforms.RandomGrayscale(p=0.2),
                transforms.ToTensor(), 
                transforms.Normalize(normalize_mean, normalize_std) # the mean and std on cifar training set
                ])
            self.strong_transform = transforms.Compose([
                transforms.ToPILImage(),
                transforms.Resize((32, 32)),
                transforms.RandomResizedCrop(size=32, scale=(0.2, 1.)),
                transforms.RandomHorizontalFlip(),
                RandomAugment(3, 5),
                transforms.ToTensor(), 
                transforms.Normalize(normalize_mean, normalize_std) # the mean and std on cifar training set
                ])
        else:
            self.test_transform = transforms.Compose([
                transforms.ToPILImage(),
                transforms.Resize((32, 32)),
                transforms.ToTensor(),
                transforms.Normalize(normalize_mean, normalize_std),
                ])


    def __len__(self):
        return len(self.dlabels)
        
    def __getitem__(self, index):
        if self.train_flag == True:
            each_image_w1 = self.weak_transform(self.images[index])
            each_image_s1 = self.strong_transform(self.images[index])
            each_plabel = self.plabels[index]
            each_dlabel = self.dlabels[index]
            return each_image_w1, each_image_s1,each_plabel, each_dlabel, index
        else:
            each_image = self.test_transform(self.images[index])
            each_dlabel = self.dlabels[index]
            return each_image, each_dlabel
