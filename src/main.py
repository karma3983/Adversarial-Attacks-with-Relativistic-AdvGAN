# Adversarial Attacks with AdvGAN and AdvRaGAN
# Copyright(C) 2020 Georgios (Giorgos) Karantonis
#
# This program is free software: you can redistribute it and / or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

import os
import json

import numpy as np

import torch
import torchvision.datasets
import torch.nn.functional as F
import torchvision.transforms as transforms
from torch.utils.data import DataLoader
from torchvision.utils import save_image
import torchvision.models as m
from torch.utils.data.sampler import SubsetRandomSampler

import models
import custom_data as cd
from advGAN import AdvGAN_Attack



def load_hyperparameters(config_file):
    with open(config_file) as hp_file:
        hyperparams = json.load(hp_file)

    target = hyperparams['target_dataset']
    lr_target = hyperparams['target_learning_rate']
    epochs_target = hyperparams['target_model_epochs']
    l_inf_bound = hyperparams['maximum_perturbation_allowed']

    epochs = hyperparams['AdvGAN_epochs']
    lr = hyperparams['AdvGAN_learning_rate']
    alpha = hyperparams['alpha']
    beta = hyperparams['beta']
    gamma = hyperparams['gamma']
    kappa = hyperparams['kappa']
    c = hyperparams['c']
    n_steps_D=hyperparams['D_number_of_steps_per_batch']
    n_steps_G = hyperparams['G_number_of_steps_per_batch']
    is_relativistic = True if hyperparams['is_relativistic'] == 'True' else False

    return target, lr_target, epochs_target, l_inf_bound, epochs, lr, alpha, beta, gamma, kappa, c, n_steps_D, n_steps_G, is_relativistic


def create_dirs():
    if not os.path.exists('./results/examples/MNIST/train/'):
        os.makedirs('./results/examples/MNIST/train/')

    if not os.path.exists('./results/examples/MNIST/test/'):
        os.makedirs('./results/examples/MNIST/test/')

    if not os.path.exists('./results/examples/CIFAR10/train/'):
        os.makedirs('./results/examples/CIFAR10/train/')

    if not os.path.exists('./results/examples/CIFAR10/test/'):
        os.makedirs('./results/examples/CIFAR10/test/')

    if not os.path.exists('./results/examples/HighResolution/train/'):
        os.makedirs('./results/examples/HighResolution/train/')

    if not os.path.exists('./results/examples/HighResolution/test/'):
        os.makedirs('./results/examples/HighResolution/test/')

    if not os.path.exists('./checkpoints/target/'):
        os.makedirs('./checkpoints/target/')

    if not os.path.exists('./npy/MNIST/'):
        os.makedirs('./npy/MNIST/')

    if not os.path.exists('./npy/CIFAR10/'):
        os.makedirs('./npy/CIFAR10/')

    if not os.path.exists('./npy/HighResolution/'):
        os.makedirs('./npy/HighResolution/')


def init_params(target):
    if target == 'MNIST':
        batch_size = 128
        l_inf_bound = .3 if L_INF_BOUND == 'Auto' else L_INF_BOUND

        n_labels = 10
        n_channels = 1

        target_model = models.MNIST_target_net().to(device)

        train_dataset = torchvision.datasets.MNIST('./datasets', train=True, transform=transforms.ToTensor(), download=True)
        test_dataset = torchvision.datasets.MNIST('./datasets', train=False, transform=transforms.ToTensor(), download=True)

        train_dataloader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, num_workers=1)
        test_dataloader = DataLoader(test_dataset, batch_size=batch_size, shuffle=True, num_workers=1)
    elif target == 'CIFAR10':
        batch_size = 400
        l_inf_bound = 8/255 if L_INF_BOUND == 'Auto' else L_INF_BOUND/255

        n_labels = 10
        n_channels = 3

        target_model = models.resnet32().to(device)

        train_dataset = torchvision.datasets.CIFAR10('./datasets', train=True, transform=transforms.ToTensor(), download=True)
        test_dataset = torchvision.datasets.CIFAR10('./datasets', train=False, transform=transforms.ToTensor(), download=True)

        train_dataloader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, num_workers=1)
        test_dataloader = DataLoader(test_dataset, batch_size=batch_size, shuffle=True, num_workers=1)
    elif target == 'HighResolution':
        batch_size = 70
        l_inf_bound = .01 if L_INF_BOUND == 'Auto' else L_INF_BOUND
        
        n_labels = 1000
        n_channels = 3

        target_model = m.inception_v3(pretrained=True).to(device)
        target_model.eval()

        transform = transforms.Compose([
                            transforms.Resize(299), 
                            transforms.ToTensor(), 
                            transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
                        ])

        dataset = cd.HighResolutionDataset('./datasets/high_resolution/img', transform=transform)

        train_dataset, test_dataset = cd.split_dataset(dataset)
        train_sampler = SubsetRandomSampler(train_dataset)
        test_sampler = SubsetRandomSampler(test_dataset)

        train_dataloader = DataLoader(dataset, batch_size=batch_size, sampler=train_sampler)
        test_dataloader = DataLoader(dataset, batch_size=batch_size, sampler=test_sampler)
    else:
        raise NotImplementedError('Unknown Dataset')

    return train_dataloader, test_dataloader, target_model, batch_size, l_inf_bound, n_labels, n_channels, len(test_dataset)


def train_target_model(target, target_model, epochs, train_dataloader, test_dataloader, dataset_size):
    target_model.train()
    optimizer = torch.optim.Adam(target_model.parameters(), lr=LR_TARGET_MODEL)
    
    for epoch in range(epochs):
        loss_epoch = 0

        for i, data in enumerate(train_dataloader, 0):

            train_imgs, train_labels = data
            train_imgs, train_labels = train_imgs.to(device), train_labels.to(device)

            logits_model = target_model(train_imgs)
            criterion = F.cross_entropy(logits_model, train_labels) # 交差エントロピー誤差
            loss_epoch += criterion
            
            optimizer.zero_grad() # 勾配を0に
            criterion.backward() # 誤差逆伝播
            optimizer.step() # 内部に保存されているgradを更新して反復処理

        print('Loss in epoch {}: {}'.format(epoch, loss_epoch.item()))

    # save model
    targeted_model_file_name = './checkpoints/target/{}_bs_{}_lbound_{}.pth'.format(target, batch_size, l_inf_bound)
    torch.save(target_model.state_dict(), targeted_model_file_name)
    target_model.eval()

    n_correct = 0
    for i, data in enumerate(test_dataloader, 0):
        test_img, test_label = data
        test_img, test_label = test_img.to(device), test_label.to(device)
        
        pred_lab = torch.argmax(target_model(test_img), 1)
        n_correct += torch.sum(pred_lab == test_label,0)

    print('{} test set:'.format(target))
    print('Correctly Classified: ', n_correct.item())
    print('Accuracy in {} test set: {}%\n'.format(target, 100 * n_correct.item()/dataset_size))


def test_attack_performance(target, dataloader, mode, adv_GAN, target_model, batch_size, l_inf_bound, dataset_size):
    n_correct = 0

    true_labels, pred_labels = [], []
    img_np, adv_img_np = [], []
    for i, data in enumerate(dataloader, 0):
        img, true_label = data
        img, true_label = img.to(device), true_label.to(device)
        
        perturbation = adv_GAN(img)

        adv_img = torch.clamp(perturbation, -l_inf_bound, l_inf_bound) + img
        adv_img = torch.clamp(adv_img, 0, 1)
        
        pred_label = torch.argmax(target_model(adv_img), 1)
        n_correct += torch.sum(pred_label == true_label, 0)

        true_labels.append(true_label.cpu().numpy())
        pred_labels.append(pred_label.cpu().numpy())
        img_np.append(img.detach().permute(0, 2, 3, 1).cpu().numpy())
        adv_img_np.append(adv_img.detach().permute(0, 2, 3, 1).cpu().numpy())


        print('Saving images for batch {} out of {}'.format(i+1, len(dataloader)))
        for j in range(adv_img.shape[0]):
            cur_img = adv_img[j].detach()
            
            if target == 'HighResolution':
                inv_norm = cd.NormalizeInverse(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
                cur_img = inv_norm(img[j])

                save_image(cur_img + perturbation[j], './results/examples/{}/{}/example_{}_{}.png'.format(target, mode, i, j))
            else:
                save_image(cur_img, './results/examples/{}/{}/example_{}_{}.png'.format(target, mode, i, j))


    true_labels = np.concatenate(true_labels, axis=0)
    pred_labels = np.concatenate(pred_labels, axis=0)
    img_np = np.concatenate(img_np, axis=0)
    adv_img_np = np.concatenate(adv_img_np, axis=0)

    np.save('./npy/{}/true_labels'.format(target), true_labels)
    np.save('./npy/{}/pred_labels'.format(target), pred_labels)
    np.save('./npy/{}/img_np'.format(target), img_np)
    np.save('./npy/{}/adv_img_np'.format(target), adv_img_np)

    print(target)
    print('Correctly Classified: ', n_correct.item())
    print('Accuracy under attacks in {} {} set: {}%\n'.format(target, mode, 100 * n_correct.item()/dataset_size))
    
    # pltの表示（追加）----------------------------------------------------------------------------------------------------------------
    n = 0
    one = 1
    two = 2
    plt.figure(figsize=(24,12))
    for i in range(9):
        # print("real Num",i+1)

        plt.subplot(3,6,one)
        one = one + 2

        # 本物の画像とラベル
        plt.imshow(img[i].cpu().detach().numpy().reshape(28,28))
        plt.title("label: {}".format(true_label[i].item()), fontsize=18) #タイトル
        plt.gray()

        two = two + 2
        
        # 偽物の画像と予測値（予測ラベル）
        # plt.imshow(cur_img[i].cpu().detach().numpy().reshape(28,28))
        plt.imshow(cur_img[i].cpu().numpy().reshape(28,28))
        plt.title("pred label: {}".format(pred_label[i].item()), fontsize=18) #タイトル
        plt.gray()  

    plt.show()


# ここから実行----------------------------------------------------------------------------------------------------

# print('\nLOADING CONFIGURATIONS...')
print('\n設定をロード中...')
TARGET, LR_TARGET_MODEL, EPOCHS_TARGET_MODEL, L_INF_BOUND, EPOCHS, LR, ALPHA, BETA, GAMMA, KAPPA, C, N_STEPS_D, N_STEPS_G, IS_RELATIVISTIC = load_hyperparameters('hyperparams.json')


# print('\nCREATING NECESSARY DIRECTORIES...')
print('\n必要なディレクトリを作成中...')
create_dirs()


# Define what device we are using
# print('\nCHECKING FOR CUDA...')
print('\nCUDAをチェック中...')
use_cuda = True
print('CUDA Available: ',torch.cuda.is_available())
device = torch.device('cuda' if (use_cuda and torch.cuda.is_available()) else 'cpu')


# print('\nPREPARING DATASETS...')
print('\nデータセットを準備中...')
# MNIST or HighResolution or CIFAR10
train_dataloader, test_dataloader, target_model, batch_size, l_inf_bound, n_labels, n_channels, test_set_size = init_params(TARGET)

if TARGET != 'HighResolution':
    # print('CHECKING FOR PRETRAINED TARGET MODEL...')
    print('学習済のターゲットモデルをチェック中...')
    try:
        # ./checkpoints/target/MNIST_bs_128_lbound_.3.pth
        pretrained_target = './checkpoints/target/{}_bs_{}_lbound_{}.pth'.format(TARGET, batch_size, l_inf_bound)
        target_model.load_state_dict(torch.load(pretrained_target))
        target_model.eval()
    except FileNotFoundError:
        # print('\tNO PRETRAINED MODEL FOUND... TRAINING TARGET FROM SCRATCH...') 
        print('\t学習済モデルが見つかりませんでした... 一からターゲットを学習させます...') 
        train_target_model(
                            target=TARGET, 
                            target_model=target_model, 
                            epochs=EPOCHS_TARGET_MODEL, 
                            train_dataloader=train_dataloader, 
                            test_dataloader=test_dataloader, 
                            dataset_size=test_set_size
                        )
# print('TARGET LOADED!')
print('ターゲットロード完了')


# train AdvGAN
# print('\nTRAINING ADVGAN...')
print('\nADVGANを学習中...')
advGAN = AdvGAN_Attack(
                        device, 
                        target_model, 
                        n_labels, 
                        n_channels, 
                        target=TARGET, 
                        lr=LR, 
                        l_inf_bound=l_inf_bound, 
                        alpha=ALPHA, 
                        beta=BETA, 
                        gamma=GAMMA, 
                        kappa=KAPPA, 
                        c=C, 
                        n_steps_D=N_STEPS_D, 
                        n_steps_G=N_STEPS_G, 
                        is_relativistic=IS_RELATIVISTIC
                    )
advGAN.train(train_dataloader, EPOCHS)


# load the trained AdvGAN
# print('\nLOADING TRAINED ADVGAN!')
print('\n学習済ADVGANのロード完了')
adv_GAN_path = './checkpoints/AdvGAN/G_epoch_{}.pth'.format(EPOCHS)
adv_GAN = models.Generator(n_channels, n_channels, TARGET).to(device)
adv_GAN.load_state_dict(torch.load(adv_GAN_path))
adv_GAN.eval()


# print('\nTESTING PERFORMANCE OF ADVGAN...')
print('\nADVGANのパフォーマンスをテスト中...')
test_attack_performance(target=TARGET, dataloader=test_dataloader, mode='test', adv_GAN=adv_GAN, target_model=target_model, batch_size=batch_size, l_inf_bound=l_inf_bound, dataset_size=test_set_size)
