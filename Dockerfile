# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY src/ ./src/

# Set the PYTHONPATH to include the src directory
ENV PYTHONPATH=/app/src

# Make port 8501 available to the world outside this container
EXPOSE 8501

# Run the streamlit application
CMD ["python", "-m", "streamlit", "run", "src/energy_explore/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
