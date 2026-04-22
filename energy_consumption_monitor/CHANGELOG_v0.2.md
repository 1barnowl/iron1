apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: true
    jsonData:
      timeInterval: "5s"

  - name: TimescaleDB
    type: postgres
    access: proxy
    url: timescaledb:5432
    database: energy_monitor
    user: energy_user
    secureJsonData:
      password: change_me_in_production
    jsonData:
      sslmode: disable
      postgresVersion: 1400
      timescaledb: true
    editable: true
