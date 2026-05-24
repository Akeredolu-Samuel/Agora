FROM python:3.11-slim

# Create a non-root user (required by Hugging Face Spaces)
RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH"

WORKDIR /app

# Copy files and ensure the non-root user owns them
COPY --chown=user:user requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=user:user . .

# Expose port 7860
EXPOSE 7860

# Run the bot
CMD ["python", "main.py"]
