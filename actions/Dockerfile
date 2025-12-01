FROM rasa/rasa-sdk:latest

USER root
WORKDIR /app

# Copy requirements của action server (nếu có)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy code vào thư mục /app/actions
# Lưu ý: Vì context ở docker-compose là ./actions, nên COPY . nghĩa là copy nội dung folder actions
COPY . /app/actions

USER 1001

# Vì code nằm trong /app/actions, lệnh này là chính xác
CMD ["start", "--actions", "actions"]