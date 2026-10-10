# PRD: Sentio — AI Learning Copilot

## Product Overview

Sentio is an AI-powered Learning Copilot designed for college students. It combines personalized tutoring, long-term student memory, document-based knowledge retrieval, learning analytics, emotion-aware adaptation, and multi-agent AI workflows to help students achieve deeper conceptual understanding.

Unlike traditional AI chatbots, Sentio continuously learns about each student, tracks learning progress, identifies weak areas, adapts explanations based on learning state, and provides grounded answers using the student's own study materials.

---

# Problem Statement

## What problem does this solve?

College students often struggle with:

* Information overload from textbooks, notes, lectures, and assignments.
* Generic AI tutors that do not remember prior learning history.
* Difficulty identifying weak concepts and knowledge gaps.
* Lack of personalized explanations tailored to learning style and progress.
* Inefficient revision and study planning.
* Fragmented learning across multiple resources.

## Who experiences this problem?

Primary users are college students studying academic subjects that require sustained conceptual understanding and long-term retention.

## Why does this matter now?

AI tools are becoming common in education, but most function as stateless chat assistants. Students need an intelligent learning companion that understands their learning journey, adapts to their progress, and provides personalized academic support grounded in their own study materials.

---

# Target User

## Primary User

College students aged approximately 18–25.

## User Goals

* Understand difficult concepts more effectively.
* Learn from personal study materials.
* Track academic progress.
* Identify and improve weak areas.
* Prepare for exams efficiently.
* Receive personalized tutoring.

## User Frustrations

* Forgetting previously learned material.
* Generic explanations that do not match their understanding level.
* Difficulty organizing study resources.
* Lack of personalized guidance.
* Spending excessive time searching for answers.

## User Behaviors

* Upload PDFs, notes, slides, and assignments.
* Study in multiple sessions across weeks or months.
* Ask follow-up questions frequently.
* Revise before exams.
* Learn at different speeds depending on subject difficulty.

---

# Core Features (MVP)

## Feature 1: AI Tutor Chat [PASS]

### Description

A conversational AI tutor that answers questions, explains concepts, and guides learning through personalized interactions.

### Capabilities

* Natural language chat.
* Context-aware explanations.
* Follow-up question support.
* Multiple explanation styles.
* Step-by-step teaching mode.

### Importance

This is the core learning experience and primary user interface.

---

## Feature 2: Source-Aware Document Knowledge System [PASS]

### Description

Students upload learning materials and interact with them through AI-powered retrieval.

### Supported Files

* PDF
* DOCX
* TXT
* Lecture Notes
* Slides

### Capabilities

* Document ingestion.
* Semantic search.
* Retrieval-Augmented Generation (RAG).
* Source citations.
* Grounded question answering.

### Importance

Provides trustworthy answers based on the student's own content.

---

## Feature 3: Persistent Student Memory [PASS]

### Description

Long-term memory system that stores and updates a personalized learning profile.

### Stored Data

* Studied topics.
* Mastery levels.
* Weak areas.
* Strong areas.
* Learning preferences.
* Learning goals.
* Assessment history.
* Session summaries.

### Capabilities

* Personalized tutoring.
* Learning continuity.
* Adaptive recommendations.
* Progress tracking.

### Importance

Differentiates Sentio from traditional AI chatbots.

---

## Feature 4: Learning Analytics & Weak Area Detection [PASS]

### Description

Continuously evaluates learning progress and identifies knowledge gaps.

### Capabilities

* Topic mastery tracking.
* Weak concept identification.
* Progress dashboards.
* Learning trend analysis.
* Revision recommendations.

### Metrics Tracked

* Questions asked.
* Quiz performance.
* Topic coverage.
* Confidence trends.

### Importance

Ensures learning improvement rather than simple question answering.

---

## Feature 5: Adaptive Tutoring Engine [PASS]

### Description

Adjusts tutoring strategies based on student behavior and inferred learning state.

### Learning States

* Engaged
* Confused
* Frustrated
* Neutral
* Confident

### Input Signals

#### Primary

* Chat sentiment analysis.

#### Secondary (Optional)

* Webcam facial analysis.

### Adaptive Actions

* Simplify explanations.
* Provide examples.
* Slow down teaching pace.
* Recommend revision.
* Increase challenge level.

### Importance

Creates a personalized and human-like tutoring experience.

---

# Nice-to-Have Features (Not Required for Launch)

* Flashcard generation. [PASS]
* Quiz generation. [PASS]
* Study plan generation. [PARTIAL]
* Voice interaction. [PASS]
* Voice emotion analysis. [FAIL]
* Mobile application. [FAIL]
* Group study mode. [FAIL]
* Peer collaboration. [FAIL]
* LMS integrations. [FAIL]
* Competitive exam specialization. [FAIL]
* Gamification. [FAIL]
* AI-generated summaries. [PASS]
* Recorded lecture ingestion. [FAIL]

---

# Out of Scope (v1)

The following features will NOT be built in the first release:

* Mobile apps.
* Voice-based tutoring.
* Speech emotion analysis.
* Video lecture processing.
* Real-time classroom integrations.
* Teacher dashboards.
* Institution management.
* Marketplace functionality.
* Subscription billing.
* Social learning features.
* Peer discussion forums.
* Live human tutors.
* Multiplayer collaboration.

---

# Success Metrics

## Primary Success Metric

### Concept Understanding Improvement

Measure improvement through quiz performance and topic mastery progression.

Target:

* 25% improvement in topic mastery scores after 30 days.

---

## KPI 1

### Weekly Active Students (WAU)

Target:

* 500+ active students during initial beta.

---

## KPI 2

### Session Completion Rate

Definition:
Percentage of tutoring sessions completed without abandonment.

Target:

* Greater than 70%.

---

## KPI 3

### Weak Area Improvement Rate

Definition:
Percentage of identified weak topics showing measurable improvement.

Target:

* Greater than 60%.

---

# Technical Assumptions

## Platform

* Web Application Only

---

## Frontend

* Next.js
* TypeScript
* Tailwind CSS
* Shadcn UI

---

## Backend

* FastAPI
* Python

---

## Database

* PostgreSQL

---

## Vector Database

* ChromaDB (initial)
  or
* Qdrant (production-ready option)

---

## Authentication

* Google OAuth
* Email/Password Authentication

---

## AI Infrastructure

### Local-First AI Stack

* Ollama

Supported Models:

* Llama
* Mistral
* Qwen
* Gemma
* Phi
* DeepSeek

---

## Multi-Agent Architecture

Suggested Agents:

### Tutor Agent

Handles teaching and explanations.

### Memory Agent

Maintains student profiles and long-term memory.

### Retrieval Agent

Manages RAG and document retrieval.

### Analytics Agent

Tracks progress and identifies weak areas.

### Adaptation Agent

Adjusts tutoring strategy based on learning state.

---

## Emotion Detection

### Text-Based

* Sentiment classification.
* Learning-state inference.

### Webcam-Based (Optional)

* Facial engagement analysis.
* Frustration/confusion detection.

---

## Storage

Store:

* User profiles.
* Learning history.
* Session summaries.
* Uploaded documents.
* Embeddings.
* Analytics data.

---

# Open Questions

## 1. How should mastery scores be calculated?

Options:

* Quiz-based.
* Interaction-based.
* Hybrid model.

---

## 2. Should emotion detection require explicit consent every session?

Privacy and compliance decision required.

---

## 3. How much historical memory should be retained?

Options:

* Unlimited.
* Semester-based.
* User-controlled retention.

---

## 4. What is the optimal multi-agent orchestration strategy?

Options:

* Sequential workflow.
* Dynamic routing.
* Planner-executor architecture.

---

## 5. Should flashcards and quizzes be included in MVP or Phase 2?

Requires user validation and prioritization.

---

# MVP Definition

A successful Sentio v1 allows a college student to:

1. Create an account. [PASS]
2. Upload study materials. [PASS]
3. Ask questions about uploaded content. [PASS]
4. Receive source-grounded explanations. [PASS]
5. Maintain learning history across sessions. [PASS]
6. Track progress and weak areas. [PASS]
7. Receive adaptive tutoring based on learning state. [PASS]

If these capabilities work reliably and improve conceptual understanding, Sentio v1 is considered successful.
