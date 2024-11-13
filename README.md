## Sensorlog Realtime Visualization

```bash
sudo yum install git
sudo yum install -y tmux

python3 -m venv venv
source venv/bin/activate
pip install fastapi uvicorn
git clone https://github.com/earthinversion/sensor_logger_app_http_push_server.git

# ## install redis from source
# sudo yum install -y gcc jemalloc-devel
# curl -O http://download.redis.io/redis-stable.tar.gz
# tar xzvf redis-stable.tar.gz
# cd redis-stable
# make
# sudo make install


python3 -m venv venv
source venv/bin/activate
pip install pandas
pip install Flask Flask-SocketIO eventlet
pip install matplotlib
pip install streamlit
pip install streamlit-autorefresh
pip install sqlite3
pip install plotly


git clone https://github.com/earthinversion/smartphone_sensor_data_acquisition.git
cd smartphone_sensor_data_acquisition

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
<!-- - http://54.245.66.246:5000/ -->
- http://35.89.184.162:5000/

## Starting and stopping the service
```bash
chmod +x start_services.sh
./start_services.sh
```

```bash
# Find and kill the TCP server process
pkill -f "python tcp_server_db.py"

# Find and kill the Streamlit app process
pkill -f "streamlit run streamlit_app.py"

```



## Using tmux to run
```bash
tmux new -s tcp_server
python tcp_server_db.py

tmux new -s waveform_stream
streamlit run streamlit_app.py --server.port 5000
```

- To attach again to sessions
```bash
tmux attach -t tcp_server
tmux attach -t waveform_stream
```

## Download the db from the EC2 instance to local
```bash
scp -i "sensor_log.pem" ec2-user@ec2-54-245-66-246.us-west-2.compute.amazonaws.com:/home/ec2-user/smartphone_sensor_data_acquisition/sensor_data.db .
```

## References
- https://sensorlog.berndthomas.net/
- https://www.berndthomas.net/
- https://apps.apple.com/us/app/sensorlog/id388014573