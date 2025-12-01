FROM rasa/rasa:3.6.21

USER root

WORKDIR /app

# 1. Copy requirements trước để tận dụng cache (nếu không đổi thư viện thì không cần cài lại)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 2. Copy toàn bộ code (ngoại trừ những gì trong .dockerignore)
COPY . /app

# 3. Đảm bảo user 1001 sở hữu các file này để tránh lỗi Permission
RUN chown -R 1001:1001 /app

USER 1001

# LƯU Ý: Không chạy 'rasa train' ở đây. 
# Nếu chưa có model, container sẽ báo lỗi và restart. Xem hướng dẫn train bên dưới.

CMD ["run", "--enable-api", "--cors", "*", "--debug"]