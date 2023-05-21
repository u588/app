images=(
kube-apiserver:v1.21.14
kube-controller-manager:v1.21.14
kube-scheduler:v1.21.14
kube-proxy:v1.21.14
pause:3.4.1
coredns/coredns:1.8.0
etcd:3.4.13-0
)

for imageName in ${images[@]} ; do
docker pull registry.cn-hangzhou.aliyuncs.com/google_containers/$imageName
docker tag registry.cn-hangzhou.aliyuncs.com/google_containers/$imageName k8s.gcr.io/$imageName
docker rmi registry.cn-hangzhou.aliyuncs.com/google_containers/$imageName
done
