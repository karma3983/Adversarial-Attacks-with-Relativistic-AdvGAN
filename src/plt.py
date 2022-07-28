import torch
import torchvision.datasets
# import torchvision.transforms as transforms
# from torch.utils.data import DataLoader
import matplotlib.pyplot as plt
from main import train_target_model # 追加
from main import test_attack_performance # 追加

n = 0
one = 1
two = 2
plt.figure(figsize=(24,12))
for i in range(9):
  # print("real Num",i+1)

  plt.subplot(3,6,one)
  one = one + 2

  plt.imshow(test_attack_performance.img[i].cpu().detach().numpy().reshape(28,28))
  plt.title("label: {}".format(test_attack_performance.true_label[i].item()), fontsize=18) #タイトル
  plt.gray()
  #plt.show()

  two = two + 2

  plt.imshow(test_attack_performance.adv_img[i].cpu().detach().numpy().reshape(28,28))
  plt.title("pred label: {}".format(test_attack_performance.pred_label[i].item()), fontsize=18) #タイトル
  plt.gray()  

plt.show()
