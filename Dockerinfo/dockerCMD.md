# docker制作

## 原始镜像（docker/trixie3.13:v0）== 干净系统空Python包

* Debian版本13(trixie)
* Python3.13.7
* apt、pip已换国内源
* 系统2025.9更新
* docker run -d docker/trixie3.13:v0
* docker exec -it CID bash

## 制作Docker

* docker build -t (目标镜像名) -f ./dockerfile文件 .
* docker build -t 10.3.18.60/docker/tdx-scrape:u1 -f ./Dockerfile .
  
## docker相关命令

### 镜像运行后自停

* docker run -d  docker.m.daocloud.io/library/python:3.13.7-trixie tail -f /dev/null

## docker镜像tag查找

* <https://1ms.run/>
* docker pull docker.1ms.run/library/ubuntu:22.04 -->  docker.m.daocloud.io
  