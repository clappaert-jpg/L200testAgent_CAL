FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CAL_FLASH_MODEL="gemini-3.8-flash" \
    CAL_PRO_MODEL="gemini-3.1-pro" \
    CAL_SESSION_DB_PATH="/var/lib/cal_agent/kuwait_cal_sessions.db"

WORKDIR /app

RUN mkdir -p /var/lib/cal_agent

COPY pyproject.toml README.md run_sunday_dashboard.py ./
COPY kuwait_cal_agent ./kuwait_cal_agent
COPY evals ./evals
COPY tests ./tests

RUN pip install --no-cache-dir -e .

CMD ["python3", "run_sunday_dashboard.py", "--once"]
