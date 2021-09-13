if __name__ == '__main__':
    import torch
    import time
    import os
    import torchvision.datasets as dset
    import torchvision.transforms as transforms
    import torchvision.utils as vutils

    import numpy as np
    import random
    import torch.nn as nn
    import torch.nn.parallel

    import matplotlib.pyplot as plt
    # 先尝试加载数据并且显示图片吧

    import torch.optim as optim

    dataroot = "image"
    image_size = 64

    batch_size = 64
    workers = 6

    ngpu = 1
    nc = 3
    nz = 100
    ngf = 64
    ndf = 64

    num_epochs = 5
    lr = 0.0002
    beta1 = 0.5

    dataset = dset.ImageFolder(root=dataroot,
                               transform=transforms.Compose([
                                   transforms.Resize(image_size),
                                   transforms.CenterCrop(image_size),
                                   transforms.ToTensor(),  # 将灰度范围从0-255变换到0-1
                                   transforms.Normalize((0.5, 0.5, 0.5), (0.5, 0.5, 0.5)),  # 将灰度范围从0-1变化到-1到1
                               ]))

    dataloader = torch.utils.data.DataLoader(dataset, batch_size=batch_size,
                                             shuffle=False,  # 这里应该是决定是否打乱顺序
                                             num_workers=workers,
                                             )

    device = torch.device("cuda:0" if (torch.cuda.is_available() and ngpu > 0) else "cpu")


    fixed_noise = torch.randn(64, nz, 1, 1, device=device)

    # 设计真假标签
    real_label = 1.0
    fake_label = 0.0

    criterion = nn.BCELoss()

    # 开始写模型的代码
    class Generator(nn.Module):
        def __init__(self, ngpu):
            super(Generator, self).__init__()  # 用父类的方法来初始化自己，嗯...意思就是
            # 继承自父类的参数，由父类自己的初始化方法来初始化
            self.ngpu = ngpu
            self.main = nn.Sequential(
                nn.ConvTranspose2d(nz, ndf * 8, 4, 1, 0, bias=False),
                nn.BatchNorm2d(ngf * 8),
                nn.ReLU(True),

                nn.ConvTranspose2d(ngf * 8, ngf * 4, 4, 2, 1, bias=False),
                nn.BatchNorm2d(ngf * 4),
                nn.ReLU(True),
                # state size. (ngf*4) x 8 x 8
                nn.ConvTranspose2d(ngf * 4, ngf * 2, 4, 2, 1, bias=False),
                nn.BatchNorm2d(ngf * 2),
                nn.ReLU(True),
                # state size. (ngf*2) x 16 x 16
                nn.ConvTranspose2d(ngf * 2, ngf, 4, 2, 1, bias=False),
                nn.BatchNorm2d(ngf),
                nn.ReLU(True),
                # state size. (ngf) x 32 x 32
                nn.ConvTranspose2d(ngf, nc, 4, 2, 1, bias=False),
                nn.Tanh()
            )

        def forward(self, input):
            return self.main(input)


    # 判别器的定义
    class Discriminator(nn.Module):
        def __init__(self, ngpu):
            super(Discriminator, self).__init__()
            self.ngpu = ngpu
            self.main = nn.Sequential(
                nn.Conv2d(nc, ndf, 4, 2, 1, bias=False),
                nn.LeakyReLU(0.2, inplace=True),

                nn.Conv2d(ndf, ndf * 2, 4, 2, 1, bias=False),
                nn.BatchNorm2d(ndf * 2),
                nn.LeakyReLU(0.2, inplace=True),

                nn.Conv2d(ndf * 2, ndf * 4, 4, 2, 1, bias=False),
                nn.BatchNorm2d(ndf * 4),
                nn.LeakyReLU(0.2, inplace=True),

                nn.Conv2d(ndf * 4, ndf * 8, 4, 2, 1, bias=False),
                nn.BatchNorm2d(ndf * 8),
                nn.LeakyReLU(0.2, inplace=True),

                nn.Conv2d(ndf * 8, 1, 4, 1, 0, bias=False),
                nn.Sigmoid()

            )

        def forward(self, input):
            return self.main(input)


    netG = Generator(ngpu).to(device)
    if (device.type == 'cuda') and (ngpu > 1):
        netG = nn.DataParallel(netG, list(range(ngpu)))

    netD = Discriminator(ngpu).to(device)

    if (device.type == 'cuda') and (ngpu > 1):
        netD = nn.DataParallel(netD, list(range(ngpu)))

    netG = torch.load(os.path.join('.','mymodel\\netG.pth'))
    netD = torch.load(os.path.join('.','mymodel\\netD.pth'))


    img_list = []

    iters = 0
    # 开始训练

    str = time.time()

    optimizerD = optim.Adam(netD.parameters(), lr=lr, betas=(beta1, 0.999))
    optimizerG = optim.Adam(netG.parameters(), lr=lr, betas=(beta1, 0.999))

    with torch.no_grad():
        fake = netG(fixed_noise).detach().cpu()
        img_list.append(vutils.make_grid(fake, padding=2, normalize=True))

    plt.figure(figsize=(15, 15))
    plt.axis("off")
    plt.title("firts fake image")
    plt.imshow(np.transpose(img_list[0], (1, 2, 0)))
    plt.show()

    for epoch in range(num_epochs):

        for i, data in enumerate(dataloader, 0):
            # 1 update Dｎｅｔｗｏｒｋ　
            netD.zero_grad()

            real_cpu = data[0].to(device)
            b_size = real_cpu.size(0)
            label = torch.full((b_size,), real_label, device=device)

            output = netD(real_cpu).view(-1)

            errD_real = criterion(output, label)
            errD_real.backward()
            D_x = output.mean().item()  # 代表对真实数据的判断

            # train fake data
            noise = torch.randn(b_size, nz, 1, 1, device=device)
            fake = netG(noise)
            label.fill_(fake_label)
            output = netD(fake.detach()).view(-1)  # detach用于切断反向传播
            # 这里的意思相当于不会在这里对netG网络进行训练造成影响

            errD_fake = criterion(output, label)
            errD_fake.backward()

            D_G_z1 = output.mean().item()  # 代表对虚假数据的判断
            errD = errD_real + errD_fake

            optimizerD.step()

            # updateG
            netG.zero_grad()
            label.fill_(real_label)
            output = netD(fake).view(-1)

            errG = criterion(output, label)
            errG.backward()
            D_G_z2 = output.mean().item()  # 代表的是对虚假数据的判断

            optimizerG.step()



            if i % 50 == 0:
                print('[%d/%d][%d/%d]\tLoss_D: %.4f\tLoss_G: %.4f\tD(x): %.4f\tD(G(z)): %.4f / %.4f'
                      % (epoch, num_epochs, i, len(dataloader),
                         errD.item(), errG.item(), D_x, D_G_z1, D_G_z2))

            # if (iters % 500 == 0) or ((epoch == num_epochs - 1) and (i == len(dataloader) - 1)):
            #     with torch.no_grad():
            #         fake = netG(fixed_noise).detach().cpu()
            #         img_list.append(vutils.make_grid(fake, padding=2, normalize=True))
            #
            # iters += 1

    with torch.no_grad():
        fake = netG(fixed_noise).detach().cpu()
        img_list.append(vutils.make_grid(fake, padding=2, normalize=True))

    # 保存模型
    torch.save(netG, os.path.join('.', 'mymodel\\netG.pth'))
    torch.save(netD, os.path.join('.', 'mymodel\\netD.pth'))

    end = time.time()
    print("the training time is {}".format(end - str))


    plt.figure(figsize=(15, 15))
    plt.axis("off")
    plt.title("last fake image")
    plt.imshow(np.transpose(img_list[-1], (1, 2, 0)))
    plt.show()
