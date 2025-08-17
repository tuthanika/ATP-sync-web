from app import create_app
import os

app = create_app()

if __name__ == '__main__':
    # Bắt đầu ứng dụng
    port = int(os.environ.get('PORT', 52441))
    app.run(host='0.0.0.0', port=port) 