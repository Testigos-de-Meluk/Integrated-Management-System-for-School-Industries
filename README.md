# Integrated Management System for School Industries

Comprehensive enterprise management system to optimize the commercial, production, financial, and administrative processes of school industries.

This repository contains the deliverables developed by the **Testigos de Meluk** team for the Software Engineering II course.

## Course Information

- **Course:** Software Engineering II
- **Semester:** 2026-2
- **University:** National University of Colombia
- **Faculty:** Faculty of Engineering
- **Department:** Department of Systems and Industrial Engineering
- **Professor:** [Liliana Marcela Olarte Mesa](mailto:lmolartem@unal.edu.co)

## Getting Started (local development)

The whole system runs locally with **Docker Compose**: PostgreSQL, Redis, Mailpit, the Django API,
the Celery worker and scheduler, and the React frontend. You only need
[Docker Desktop](https://www.docker.com/products/docker-desktop/) (on Windows, with the WSL 2 backend).

1. Clone the repository and open a terminal in its root folder.
2. Create your local environment file (only the first time):

   ```bash
   cp .env.example .env
   ```

3. Build and start everything (the first build takes a few minutes):

   ```bash
   docker compose up --build
   ```

4. Create the first Superadministrador (only the first time; the initial password is printed once):

   ```bash
   docker compose exec backend python manage.py create_superadmin --email admin@empresa.com --name "Nombre Apellido"
   ```

5. Log in at http://localhost:5173 with that email and password. On the first login, link an
   authenticator app (Google Authenticator, Microsoft Authenticator, etc.) by scanning the QR code;
   every later login asks for its 6-digit code. Emails sent by the system (e.g. credentials of new
   accounts) appear in Mailpit.

6. Open:

   | Service | URL |
   | --- | --- |
   | Frontend (React) | http://localhost:5173 |
   | API health check | http://localhost:8000/api/health/ |
   | API documentation (Swagger UI) | http://localhost:8000/api/docs/ |
   | API documentation (ReDoc) | http://localhost:8000/api/redoc/ |
   | Mailpit (emails sent in development) | http://localhost:8025 |

Everyday commands:

| Action | Command |
| --- | --- |
| Start (after the first time) | `docker compose up` |
| Stop | `Ctrl+C`, then `docker compose down` |
| See logs of one service | `docker compose logs -f backend` |
| Open a shell in the backend | `docker compose exec backend sh` |
| Rebuild after changing `requirements/*.txt` | `docker compose up --build` |
| Rebuild after changing `package.json` | `docker compose up --build -V frontend` |
| Delete the database and start clean | `docker compose down -v` |

Code changes are picked up automatically (Django and Vite reload). The Celery worker does **not**
reload: restart it with `docker compose restart worker beat` after changing tasks.

More details: [`backend/README.md`](backend/README.md) (architecture rules and commands).

## Repository Structure

```
Integrated-Management-System-for-School-Industries/
├── backend/                    # Django + DRF + Celery (modular monolith, hexagonal modules)
│   ├── config/                 # Settings, root URLs, Celery app
│   ├── modules/                # One package per module: domain/ application/ ports/ infrastructure/
│   ├── tests/
│   ├── Dockerfile
│   └── README.md
├── frontend/                   # React + TypeScript + Vite (SPA, client-side rendering)
│   ├── src/
│   │   ├── app/                # Providers and router
│   │   ├── features/           # One folder per business feature
│   │   ├── pages/
│   │   └── shared/             # API client and shared components
│   └── Dockerfile
├── docker-compose.yml          # Local development environment
├── .env.example                # Environment variables template (copy to .env)
├── Workshops/
│   ├── Corrections/
│   │   ├── Updated-Files/
│   │   │   └── Relational_Database_Model.mmd
│   │   └── README.md
│   ├── Workshop-1/
│   │   ├── Analysis.pdf
│   │   ├── User_Story_Map_Testigos_De_Meluk.drawio
│   │   └── User_Story_Map_Testigos_De_Meluk.pdf
│   └── Workshop-2/
│       ├── Architecture Diagram/
│       │   ├── Architecture_Diagram_Testigos_De_Meluk.drawio
│       │   └── Architecture_Diagram_Testigos_De_Meluk.pdf
│       ├── Business Model Processes/
│       │   ├── Big ones/
│       │   │   ├── M2_01_Quote_Request_and_Approval.bpmn
│       │   │   ├── M2_03_Work_Order_Management.bpmn
│       │   │   └── M2_05_Customer_Management.bpmn
│       │   └── Small ones/
│       │       ├── M1_03_Session_Control.bpmn
│       │       ├── M1_04_Role_Based_Access_Control.bpmn
│       │       ├── M1_05_Automated_Backup.bpmn
│       │       ├── M2_02_Siigo_Pyme_Export.bpmn
│       │       ├── M2_04_Product_Catalog_Management.bpmn
│       │       └── M2_06_Customer_Notes.bpmn
│       ├── Class Diagram/
│       │   └── UML_Class_Diagrams_Testigos_de_Meluk.drawio
│       ├── Mockups/
│       │   ├── Backups.png
│       │   ├── Catalog.png
│       │   ├── Export Siigo.png
│       │   ├── Login.png
│       │   ├── Other views.png
│       │   ├── Quotation.png
│       │   └── Work orders.png
│       ├── Relational Database Model/
│       │   ├── Relational Database Model.mmd
│       │   └── Relational Database Model.pdf
│       └── Design.pdf
├── .gitignore
└── README.md
```

### Corrections: Pre-Implementation Baseline

| Path | Description |
| --- | --- |
| `README.md` | Corrections to Workshops 1 and 2: what changes and what is kept. Takes precedence over the original deliverables. |
| `Updated-Files/Relational_Database_Model.mmd` | Corrected relational database model (Mermaid). |

### Workshop-1: Analysis

| File | Description |
| --- | --- |
| `Analysis.pdf` | System analysis document. |
| `User_Story_Map_Testigos_De_Meluk.drawio` | Editable user story map (draw.io). |
| `User_Story_Map_Testigos_De_Meluk.pdf` | User story map in PDF format. |

### Workshop-2: Design I

| Path | Description |
| --- | --- |
| `Design.pdf` | Design report. |
| `Architecture Diagram/Architecture_Diagram_Testigos_De_Meluk.drawio` | Editable software architecture diagram (draw.io). |
| `Architecture Diagram/Architecture_Diagram_Testigos_De_Meluk.pdf` | Software architecture diagram in PDF format. |
| `Business Model Processes/Big ones/` | BPMN models of the larger business processes: Quote Request and Approval, Work Order Management, and Customer Management. |
| `Business Model Processes/Small ones/` | BPMN models of the smaller processes: Session Control, Role-Based Access Control, Automated Backup, Siigo Pyme Export, Product Catalog Management, and Customer Notes. |
| `Class Diagram/UML_Class_Diagrams_Testigos_de_Meluk.drawio` | Editable UML class diagrams (draw.io). |
| `Mockups/` | Interface mockups: Backups, Catalog, Export Siigo, Login, Other views, Quotation, and Work orders. |
| `Relational Database Model/Relational Database Model.mmd` | Editable relational database model (Mermaid). |
| `Relational Database Model/Relational Database Model.pdf` | Relational database model in PDF format. |

## Authors

**Testigos de Meluk**

- [Cristofer Damian Camilo Ordonez Osa](mailto:crordonezo@unal.edu.co)
- [Andres Felipe Franco Sepulveda](mailto:afrancose@unal.edu.co)
- [Carlos Javier Cuervo Baracaldo](mailto:ccuervoba@unal.edu.co)
- [Juan Sebastian Gil Sanchez](mailto:jgilsan@unal.edu.co)
