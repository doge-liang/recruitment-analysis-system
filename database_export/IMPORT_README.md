
# 数据库导入说明

## 导入前准备

1. 确保客户环境已安装:
   - Python 3.8+
   - MySQL 5.7+ 或 8.0+
   - 项目依赖: pip install -r requirements.txt

2. 创建数据库:
   ```sql
   CREATE DATABASE recruitment_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   CREATE USER 'recruitment_user'@'localhost' IDENTIFIED BY 'your_password';
   GRANT ALL PRIVILEGES ON recruitment_db.* TO 'recruitment_user'@'localhost';
   FLUSH PRIVILEGES;
   ```

3. 修改数据库配置:
   编辑 `recruitment_system/settings.py`:
   ```python
   DATABASES = {
       'default': {
           'ENGINE': 'django.db.backends.mysql',
           'NAME': 'recruitment_db',
           'USER': 'recruitment_user',
           'PASSWORD': 'your_password',
           'HOST': 'localhost',
           'PORT': '3306',
           'OPTIONS': {'charset': 'utf8mb4'},
       }
   }
   ```

## 导入数据

### 方法1: 使用 Django loaddata (推荐)
```bash
# 1. 先创建表结构
python manage.py migrate

# 2. 导入数据
python import_database.py
```

### 方法2: 直接运行导入脚本
```bash
python import_database.py --auto
```

## 验证导入

导入完成后，运行以下命令验证:
```bash
python manage.py shell
```

在 shell 中执行:
```python
from myApp.models import JobInfo
print(f"总记录数: {JobInfo.objects.count()}")
```

## 常见问题

1. **内存不足**: 如果 JSON 文件很大，可能需要分批导入
2. **字符编码**: 确保 MySQL 使用 utf8mb4 编码
3. **外键约束**: 导入时会自动处理依赖关系

