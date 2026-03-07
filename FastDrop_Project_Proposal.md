# Final Project – Proposal Submission

## 1. Project Description
**FastDrop** is an advanced, AI-augmented delivery and logistics management platform engineered to resolve modern supply chain bottlenecks, optimize fleet dispatching, and elevate the end-user tracking experience.

**Problem Statement:** Traditional logistics platforms suffer from siloed data, static routing, and high customer support overhead due to manual tracking inquiries and lack of real-time insights for administrators.

**Solution & Architecture:** FastDrop introduces a layered architecture. It roots its robust transactional core in a .NET Web API ecosystem, ensuring ACID compliance and secure user/shipment state management. The Frontend leverages Server-Side Rendering (SSR) via Next.js for SEO and performance, coupled with Zustand for granular state management of complex UI components (Dashboards, Live Tracking). 

**AI Integration:** The system differentiates itself through seamless integration with a Python/FastAPI AI tier. This includes a localized, bilingual (Arabic/Egyptian Dialect and English) Retrieval-Augmented Generation (RAG) chatbot using LlamaIndex to autonomously resolve customer delivery policy queries. Furthermore, it embeds a natural language Text-to-SQL Analytics Agent driven by LLMs, allowing dispatchers to query complex operational metrics (e.g., "What is the delay rate in Nasr City today?") and receive both data and AI-generated business insights.

## 2. Group Members & Roles
* **Team Leader: Ahmed Mohamed Abd EL Latief Talha**
  * *Role:* AI Features, RAG System Architecture, Part of Backend Operations.
  * *Responsibilities:* Designing the Python/FastAPI microservice, building the LlamaIndex RAG pipeline with dense/sparse retrieval, engineering Text-to-SQL logic, prompt engineering for Egyptian Arabic dialects, and bridging AI endpoints with the .NET core.
* **Team Member 2: Ahmed Mohammed Ibrahim**
  * *Role:* UI/Frontend Development, Authentication & Authorization, Full Stack / Frontend Developer (Next.js, Zustand, Shadcn).
  * *Responsibilities:* Architecting the Next.js frontend, managing global UI state via Zustand, and styling with Shadcn. Building the Home Page, secure Auth flows (Register, Login, Forget Password), Role-based Dashboards (User, Dispatcher), and CRUD pages for products and shipments.
* **Team Member 3: Ali Mohamed Ahmed**
  * *Role:* Part of Backend, Part of UI.
  * *Responsibilities:* Assisting in .NET RESTful API development, building specific CRUD features for shipments and products, and supporting UI component integration to ensure seamless data binding between frontend and backend.
* **Team Member 4: Khalid Mahmoud Hussein Mahmoud**
  * *Role:* Part of Backend.
  * *Responsibilities:* Developing core database schemas, writing optimized Entity Framework Core queries, handling backend business logic for order processing, and ensuring data integrity across the logistics pipeline.

## 3. Objectives
1. **Develop a Highly Scalable Data-Driven Core:** Construct a resilient .NET Core Web API backend implementing MVC architecture and Layered Design patterns to securely process thousands of concurrent users, shipments, and inventory items.
2. **Deploy Autonomous AI Support & Analytics:** Engineer a Python-based AI subsystem that offloads 70% of routine customer inquiries via a dialect-aware RAG Chatbot, while empowering management with an NLP-to-SQL analytics dashboard for real-time decision making.
3. **Deliver Role-Specific, Optimized Dashboards:** Create decoupled, SSR-optimized frontend interfaces tailored for disparate user roles (Customers, Dispatchers, Admins), focusing on latency reduction, intuitive CRUD operations, and real-time shipment visibility.
4. **Ensure Robust Security & State Integrity:** Implement industry-standard authorization protocols (JWT, Role-Based Access Control) alongside efficient client-side state management (Zustand) to safeguard user data across the Register, Login, and Forget Password lifecycle.

## 4. Tools & Technologies
* **Back-End (Transactional Core):** C# 12, .NET Core 8 Web API, Entity Framework Core (Code-First), MVC Design Pattern.
* **Front-End (User Interface):** React.js, Next.js (App Router), Zustand (State Management), Tailwind CSS, Shadcn UI Components, HTML5/CSS3/JavaScript (ES6+).
* **AI & Microservices (Python Tier):** Python 3.10+, FastAPI, LlamaIndex (QueryFusionRetriever), SQLAlchemy (Async), Gemini-2.5-Flash, Llama 3.3 70B, Qwen.
* **System Design:** Draw.io (FastDrop ERD Diagram, FastDrop_Class Diagram).
* **Databases:** PostgreSQL / Microsoft SQL Server.

## 5. Milestones & Deadlines
* **Milestone 1 (Weeks 1-3): Architecture, ERD, and Environment Initialization**
  * Finalize database schema, ERD, and Class Diagrams. Setup system environment.
* **Milestone 2 (Weeks 4-6): .NET Backend & Identity Foundation**
  * Deploy Auth mechanisms (JWT, roles) and core API endpoints for Products and Users CRUD operations.
* **Milestone 3 (Weeks 7-9): AI Microservices & NLP Integration**
  * Build FastAPI service. Vectorize logistics policies for RAG. Prompt-engineer Text-to-SQL logic against the DB schema.
* **Milestone 4 (Weeks 10-12): Frontend Development & API Wiring**
  * Build Next.js interfaces (Home, Login, Dispatcher Dashboard). Use Zustand for state. Connect React to APIs.
* **Milestone 5 (Deadline: June): QA, E2E Testing, & Final Presentation**
  * Execute comprehensive API tests and Frontend tests. Optimize SQL queries, resolve defects, and submit documentation.

## 6. KPIs (Key Performance Indicators)
1. **System Functionality Completion Rate:** 
   * *Metric:* Percentage of planned Epic user stories (Auth, Dashboards, CRUD, AI) pushed to production. 
   * *Target:* 100% completion verified via Agile sprint boards.
2. **Code Quality & Architecture Compliance Score:** 
   * *Metric:* Adherence to Clean Architecture (Separation of Concerns, SOLID principles) and maintainability.
   * *Target:* >90% compliance score using static analysis and peer code reviews.
3. **Testing & Reliability Rate:** 
   * *Metric:* Pass rate of automated API integration tests and critical path functional tests.
   * *Target:* >95% pass rate measured via Postman collections and unit test frameworks.
4. **Performance & Efficiency Rate:** 
   * *Metric:* System responsiveness under normal load.
   * *Target:* API response times < 300ms, AI generation times < 3s, and Frontend Time-to-Interactive < 2.5s.
5. **Error or Defect Rate:** 
   * *Metric:* Ratio of critical/high-severity bugs discovered during UAT versus total test cases.
   * *Target:* < 5% defect escape rate ensuring launch stability.
