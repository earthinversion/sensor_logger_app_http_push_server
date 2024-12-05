## Sensor logger App Realtime Visualization

```bash
sudo yum install git
sudo yum install -y tmux

## installing docker
sudo yum update -y
sudo yum install -y docker
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker ec2-user

sudo systemctl status docker.service



sudo curl -L "https://github.com/docker/compose/releases/download/$(curl -s https://api.github.com/repos/docker/compose/releases/latest | grep -Po '"tag_name": "\K.*?(?=")')/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose


## python env
python3 -m venv venv
source venv/bin/activate
pip install fastapi uvicorn
pip install plotly
pip install streamlit
pip install sqlalchemy
pip install scipy # for plotting spectrogram
pip install tables


sudo yum groupinstall "Development Tools"
sudo yum install -y postgresql-devel python3-devel

sudo dnf groupinstall "Development Tools" -y





pip install psycopg2 #to use postgresql instead of sqlite

git clone https://github.com/earthinversion/sensor_logger_app_http_push_server.git



# streamlit run streamlit_app.py --server.port 5000

python datacollection_postgresql.py #to collect smartphone data to postgresql server asynchronously
streamlit run smartphone_sensor_data.py --server.port 5000
```


## Update Security Group
1. Log in to the AWS Console and go to the EC2 Dashboard.
1. Select Security Groups:
    - In the left sidebar under Network & Security, click on Security Groups.
1. Find the Security Group:
    - Locate the Security Group associated with your EC2 instance. If you're unsure, go to the Instances section, select your instance, and check the Security Group listed in its details.
1. Edit Inbound Rules:
    - Click on the Security Group to open its details.
    - Select the Inbound rules tab, then click Edit inbound rules.
1. Add a New Rule for TCP Port 56204:
    - Click Add rule and configure it as follows:
    ```bash
    Type: Custom TCP
    Protocol: TCP
    Port Range: 56204
    Source: 0.0.0.0/0 (for all IP addresses) or specify a range that includes your phone’s IP address if you want to restrict access.
    ```
1. Save the rule.


## Access the app


## Extra
```bash
## install redis from source
sudo yum install -y gcc jemalloc-devel
curl -O http://download.redis.io/redis-stable.tar.gz
tar xzvf redis-stable.tar.gz
cd redis-stable
make
sudo make install
```