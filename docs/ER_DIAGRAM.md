# Database ER Diagram

Generated from the SQLAlchemy models by `scripts/gen_docs.py` (renders on GitHub via Mermaid).

```mermaid
erDiagram
  facilities {
    INTEGER id PK
    VARCHAR name UK
    VARCHAR location
    VARCHAR industry_type
    DATETIME created_at
  }
  model_versions {
    INTEGER id PK
    VARCHAR name
    VARCHAR kind
    VARCHAR version
    VARCHAR artifact_path
    JSON metrics
    VARCHAR data_origin
    BOOLEAN is_active
    DATETIME trained_at
  }
  roles {
    VARCHAR name PK
    VARCHAR description
  }
  system_settings {
    VARCHAR key PK
    JSON value
    DATETIME updated_at
  }
  departments {
    INTEGER id PK
    INTEGER facility_id FK
    VARCHAR name
    JSON layout
  }
  users {
    INTEGER id PK
    VARCHAR email UK
    VARCHAR full_name
    VARCHAR hashed_password
    VARCHAR role FK
    BOOLEAN is_active
    INTEGER facility_id FK
    JSON preferences
    DATETIME created_at
  }
  audit_logs {
    INTEGER id PK
    INTEGER user_id FK
    VARCHAR action
    VARCHAR entity
    VARCHAR entity_id
    JSON detail
    DATETIME created_at
  }
  documents {
    INTEGER id PK
    VARCHAR filename
    VARCHAR doc_type
    VARCHAR content_type
    INTEGER size_bytes
    TEXT text_content
    INTEGER uploaded_by_id FK
    DATETIME uploaded_at
  }
  machines {
    INTEGER id PK
    VARCHAR code UK
    VARCHAR name
    INTEGER facility_id FK
    INTEGER department_id FK
    VARCHAR machine_type
    VARCHAR status
    VARCHAR zone
    DATETIME install_date
    FLOAT operating_hours
    DATETIME last_inspection_at
    FLOAT pos_x
    FLOAT pos_y
    JSON baseline
    INTEGER assigned_engineer_id FK
    DATETIME created_at
  }
  reports {
    INTEGER id PK
    VARCHAR report_type
    VARCHAR fmt
    JSON params
    VARCHAR file_path
    INTEGER row_count
    INTEGER created_by_id FK
    DATETIME created_at
  }
  incident_reports {
    INTEGER id PK
    VARCHAR title
    TEXT description
    VARCHAR incident_type
    VARCHAR severity
    VARCHAR status
    INTEGER facility_id FK
    INTEGER department_id FK
    INTEGER machine_id FK
    INTEGER reported_by_id FK
    VARCHAR assigned_team
    DATETIME occurred_at
    DATETIME resolved_at
    TEXT resolution
    DATETIME created_at
  }
  inspection_records {
    INTEGER id PK
    INTEGER machine_id FK
    INTEGER inspector_id FK
    DATETIME inspected_at
    VARCHAR status
    TEXT notes
  }
  machine_dependencies {
    INTEGER id PK
    INTEGER source_id FK
    INTEGER target_id FK
    FLOAT weight
    VARCHAR relation
  }
  maintenance_records {
    INTEGER id PK
    INTEGER machine_id FK
    VARCHAR title
    TEXT description
    VARCHAR maint_type
    VARCHAR priority
    VARCHAR status
    VARCHAR source
    DATETIME due_date
    INTEGER assigned_to_id FK
    INTEGER created_by_id FK
    DATETIME completed_at
    TEXT completion_notes
    FLOAT risk_before
    DATETIME created_at
  }
  nlp_results {
    INTEGER id PK
    INTEGER document_id FK UK
    JSON result
    DATETIME created_at
  }
  notifications {
    INTEGER id PK
    INTEGER user_id FK
    VARCHAR title
    TEXT message
    VARCHAR level
    VARCHAR kind
    INTEGER machine_id FK
    BOOLEAN is_read
    DATETIME created_at
  }
  sensor_readings {
    INTEGER id PK
    INTEGER machine_id FK
    DATETIME timestamp
    FLOAT temperature
    FLOAT vibration
    FLOAT pressure
    FLOAT load_pct
    FLOAT shift_hours
    FLOAT production_intensity
    FLOAT weather_severity
    VARCHAR data_source
  }
  anomaly_records {
    INTEGER id PK
    INTEGER machine_id FK
    INTEGER reading_id FK
    DATETIME timestamp
    VARCHAR parameter
    FLOAT observed_value
    FLOAT expected_low
    FLOAT expected_high
    FLOAT score
    VARCHAR severity
    TEXT suggestion
    BOOLEAN acknowledged
  }
  emergency_actions {
    INTEGER id PK
    INTEGER incident_id FK
    VARCHAR category
    TEXT action
    VARCHAR status
    INTEGER performed_by_id FK
    DATETIME performed_at
    DATETIME created_at
  }
  risk_predictions {
    INTEGER id PK
    INTEGER machine_id FK
    INTEGER reading_id FK
    DATETIME timestamp
    FLOAT probability
    VARCHAR category
    VARCHAR priority
    VARCHAR model_version
    JSON features
    JSON contributions
    JSON data_quality
  }
  facilities ||--o{ departments : "facility_id"
  roles ||--o{ users : "role"
  facilities ||--o{ users : "facility_id"
  users ||--o{ audit_logs : "user_id"
  users ||--o{ documents : "uploaded_by_id"
  facilities ||--o{ machines : "facility_id"
  departments ||--o{ machines : "department_id"
  users ||--o{ machines : "assigned_engineer_id"
  users ||--o{ reports : "created_by_id"
  facilities ||--o{ incident_reports : "facility_id"
  departments ||--o{ incident_reports : "department_id"
  machines ||--o{ incident_reports : "machine_id"
  users ||--o{ incident_reports : "reported_by_id"
  machines ||--o{ inspection_records : "machine_id"
  users ||--o{ inspection_records : "inspector_id"
  machines ||--o{ machine_dependencies : "source_id"
  machines ||--o{ machine_dependencies : "target_id"
  machines ||--o{ maintenance_records : "machine_id"
  users ||--o{ maintenance_records : "assigned_to_id"
  users ||--o{ maintenance_records : "created_by_id"
  documents ||--o{ nlp_results : "document_id"
  users ||--o{ notifications : "user_id"
  machines ||--o{ notifications : "machine_id"
  machines ||--o{ sensor_readings : "machine_id"
  machines ||--o{ anomaly_records : "machine_id"
  sensor_readings ||--o{ anomaly_records : "reading_id"
  incident_reports ||--o{ emergency_actions : "incident_id"
  users ||--o{ emergency_actions : "performed_by_id"
  machines ||--o{ risk_predictions : "machine_id"
  sensor_readings ||--o{ risk_predictions : "reading_id"
```

## Tables and indexes

- **facilities** (5 columns) - indexes: -
- **model_versions** (9 columns) - indexes: ix_model_versions_name
- **roles** (2 columns) - indexes: -
- **system_settings** (3 columns) - indexes: -
- **departments** (4 columns) - indexes: ix_departments_facility_id
- **users** (9 columns) - indexes: ix_users_email
- **audit_logs** (7 columns) - indexes: ix_audit_logs_created_at
- **documents** (8 columns) - indexes: -
- **machines** (16 columns) - indexes: ix_machines_code, ix_machines_department_id, ix_machines_facility_id
- **reports** (8 columns) - indexes: -
- **incident_reports** (15 columns) - indexes: ix_incident_reports_machine_id, ix_incident_reports_occurred_at
- **inspection_records** (6 columns) - indexes: ix_inspection_records_machine_id
- **machine_dependencies** (5 columns) - indexes: ix_machine_dependencies_source_id, ix_machine_dependencies_target_id
- **maintenance_records** (15 columns) - indexes: ix_maintenance_records_machine_id
- **nlp_results** (4 columns) - indexes: -
- **notifications** (9 columns) - indexes: ix_notifications_created_at, ix_notifications_user_id
- **sensor_readings** (11 columns) - indexes: ix_readings_machine_ts
- **anomaly_records** (12 columns) - indexes: ix_anom_machine_ts
- **emergency_actions** (8 columns) - indexes: ix_emergency_actions_incident_id
- **risk_predictions** (11 columns) - indexes: ix_pred_machine_ts
