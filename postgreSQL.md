#

## 常用命令

sudo dpkg -l | grep postgre*
sudo apt install postgresql-18 postgresql-client-18  postgresql-server-dev-18 postgresql-18-pgvector
sudo -u postgres /usr/lib/postgresql/18/bin/initdb --no-data-checksums -D /data/pg18
sudo systemctl start postgresql@18-main
sudo systemctl enable postgresql@18-main
sudo systemctl status postgresql@18-main

## ======= postgres 升级 =========

### 升级准备

* 准备 pg_basebackup -h 1.1.1.56 -p 5432 -U rep -Fp -Xs -Pv  -D /data/pg16bak
* 1、16、17版安装
  * 1、安装新库
  * 2、安装pgvector插件 <https://bgithub.xyz/pgvector/pgvector>
    export PATH=$/usr/lib/postgresql/17/bin/pg_config
    /usr/bin/apt install  postgresql-17-pgvector
  * 3、安装 <https://bgithub.xyz/EnterpriseDB/system_stats>
    cd /home/ts/system_stats
    PATH="/usr/lib/postgresql/17/bin/:$PATH" make install USE_PGXS=1

``` bash
sudo -u postgres /usr/lib/postgresql/16/bin/initdb -D /data/pg16 
sudo -u postgres /usr/lib/postgresql/17/bin/initdb -D /data/pg17 
```

* 3、修改/data/pg17 下的 postgres.conf 端口号 17:5432 16:5433
* 4、完全镜像复制原始数据库
  
```bash
cp -af /data/pg16bak /data/pg16
```

* 如果pg_basebackup + -R参数, 删除/data/pg16下的 standby.signal recovery.signal

* 验证模式 

```bash
sudo -u postgres psql -c "SELECT pg_is_in_recovery()"
```

* 5、启动测试

```bash
/usr/lib/postgresql/16/bin/pg_ctl -D /data/pg16 start
有问题查看 /data/pg16/log/ 中日志
/usr/lib/postgresql/17/bin/pg_ctl -D /data/pg17 start
```

* 6、重建16版索引 原因为Linux系统升级所至

```bash
su postgres
reindexdb --concurrently --all --port 5433
```

* 7、刷新索引版本

```bash
psql -p 5433

SELECT datname FROM pg_database WHERE datistemplate = false ORDER BY datname; #列出所有数据库

ALTER DATABASE "MarkCap2024_DP"  REFRESH COLLATION VERSION;
ALTER DATABASE "StockAffs2024_DP"  REFRESH COLLATION VERSION; 
ALTER DATABASE "AffManagers2024_DP"  REFRESH COLLATION VERSION;
ALTER DATABASE "StockHolders2024_DP"  REFRESH COLLATION VERSION;
ALTER DATABASE "StockManagers2024_DP"  REFRESH COLLATION VERSION;
ALTER DATABASE "csIndex2024_discard"  REFRESH COLLATION VERSION;
ALTER DATABASE "StockFina2024_DP"  REFRESH COLLATION VERSION;
ALTER DATABASE "DataAn"  REFRESH COLLATION VERSION;
ALTER DATABASE "template1"  REFRESH COLLATION VERSION;

ALTER DATABASE "DB-GPT"  REFRESH COLLATION VERSION;
ALTER DATABASE "FindStocks"  REFRESH COLLATION VERSION;
ALTER DATABASE "Funds"  REFRESH COLLATION VERSION;
ALTER DATABASE "StockBas"  REFRESH COLLATION VERSION;
ALTER DATABASE "StockFund"  REFRESH COLLATION VERSION;
ALTER DATABASE "dify"  REFRESH COLLATION VERSION;
ALTER DATABASE "dify_plugin"  REFRESH COLLATION VERSION;
ALTER DATABASE "harbor"  REFRESH COLLATION VERSION;
ALTER DATABASE "langchain_chatchat"  REFRESH COLLATION VERSION;
ALTER DATABASE "postgres"  REFRESH COLLATION VERSION;
ALTER DATABASE "smDaily"  REFRESH COLLATION VERSION;
ALTER DATABASE "tdxFS"  REFRESH COLLATION VERSION;
ALTER DATABASE "tdxIndex"  REFRESH COLLATION VERSION;
ALTER DATABASE "tdxStocks"  REFRESH COLLATION VERSION;
```

### 升级数据库

* 1、停库

```bash
/usr/lib/postgresql/16/bin/pg_ctl -D /data/pg16 stop
/usr/lib/postgresql/17/bin/pg_ctl -D /data/pg17 stop
```

* 2、升级库

```bash
/usr/lib/postgresql/17/bin/pg_upgrade --old-datadir /data/pg16/ --new-datadir /data/pg17/ --old-bindir /usr/lib/postgresql/16/bin/ --new-bindir /usr/lib/postgresql/17/bin
/usr/lib/postgresql/18/bin/pg_upgrade --old-datadir /data/pg17/ --new-datadir /data/pg18/ --old-bindir /usr/lib/postgresql/17/bin/ --new-bindir /usr/lib/postgresql/18/bin -c
```

### 问题汇总

* 1、问题 template1

```text
-- 1. psql -p 5433
-- 2. 终止 template1 连接
-- 3. 修改 template1 属性 
-- 4. 删除 template1 
-- 5. 从 template0 重建 template1 
-- 6. 恢复模板属性
```

```bash
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'template1'; 

UPDATE pg_database SET datistemplate = false WHERE datname = 'template1'; 

DROP DATABASE template1; 

CREATE DATABASE template1 TEMPLATE = template0; 

UPDATE pg_database SET datistemplate = true WHERE datname = 'template1'; 
```

### 升级后优化

```bash
/usr/lib/postgresql/17/bin/vacuumdb --all --analyze-in-stages

/usr/lib/postgresql/18/bin/vacuumdb --all --analyze-in-stages --missing-stats-only
/usr/lib/postgresql/18/bin/vacuumdb --all --analyze-only

```

## postgresql 配置参数

```text
sudo vi /etc/postgresql/16/main/postgresql.conf 
==> listen_addresses = '*'  

sudo vim /etc/postgresql/16/main/pg_hba.conf
==> # IPv4 local connections:
     host    all             all             0.0.0.0/0               md5

sudo systemctl restart postgresql

```

```bash
sudo -i -u postgres psql

create user sa password '11111111';
create user rep password 'syslog6^';
alter user sa password '';
ALTER ROLE sa SUPERUSER;
ALTER ROLE sa CREATEROLE;
ALTER ROLE sa CREATEDB;
ALTER ROLE rep REPLICATION;

```
