# Feedback Call System

This project implements an automated feedback calling system that collects customer responses through an intelligent voice flow. It handles outbound call initiation, dynamic question logic, response validation, and structured data capture.It ensures consistent customer interactions while reducing manual effort.

# Core Components

- Voice Platform – call initiation, IVR/telephony
- ASR (Speech-to-Text) – converts audio to text
- Hybrid AI Brain – intent classifier + LLM for natural responses
- Orchestration Engine – manages the full feedback workflow
- Business Logic Layer – validation, summary creation, correction handling
- Data Layer – Excel/DB updates with full or partial feedback
- TTS (Text-to-Speech) – responds in customer's detected language

# Folder Structure

```
project-root/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── conversation.py
│   ├── schema/
│   │   ├── __init__.py
│   │   ├── feedback_request.py
│   │   ├── feedback_response.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── outbound_call_service.py
│   │   ├── feedback_flow_manager.py
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── validators.py
│   │   ├── formatter.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── call_event.py
│   │   ├── feedback_responses.py
│
├── requirements.txt
└── README.md
```
