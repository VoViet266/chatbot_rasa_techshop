FROM rasa/rasa-sdk:latest

USER root
WORKDIR /app



COPY . /app/actions

USER 1001

CMD ["start", "--actions", "actions"]
