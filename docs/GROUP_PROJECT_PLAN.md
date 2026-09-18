# MyPlaylist — Project Proposal and Team Decision Worksheet

> Working proposal for discussion. Nothing in this document becomes final until the team agrees.

## 1. Product idea

MyPlaylist is a music-focused social web application. Each user creates a profile and builds a ranked Top 10 of favourite songs. Users connect with friends, view each other's lists, react and comment, and discover music through other people.

The goal is to keep the product easy to explain while creating enough technical depth for the required `ft_transcendence` modules.

### Proposed core

- Account registration and secure login.
- User profile with avatar and online status.
- One ranked Top 10 per user.
- Mutual friend requests and friend list.
- View friends' Top 10 lists.
- Likes/dislikes and comments on Top 10 lists.
- Basic private chat.
- Music search and discovery.
- Real-time updates where they improve the experience.

### Features to consider after the core works

- Music compatibility score between users.
- Personalized recommendations.
- OAuth and 2FA.
- Notifications.
- Advanced search and filters.
- Public API.
- Analytics dashboards.
- Gamification.
- General playlists beyond the Top 10.
- One-way following.

These are possible modules or extensions, not promises. We should only add them after the core is stable.

## 2. Why this idea fits Transcendence

The subject allows a social network or creative media platform. This idea naturally supports:

- Multiple simultaneous users.
- Secure user management.
- Profiles, friends, online status, and chat.
- WebSockets and real-time notifications.
- A relational database with clear relationships.
- Search, analytics, recommendations, and external music data.
- Privacy Policy, Terms of Service, and GDPR-related features.

The application must still satisfy every mandatory requirement independently of module points.

## 3. Candidate module plan

This is a discussion starting point, not the final claim list. Every claimed module must be complete and demonstrable.

| Module | Type | Points | Product use |
| --- | --- | ---: | --- |
| Framework for frontend and backend | Major | 2 | Application foundation |
| Real-time features | Major | 2 | Chat, presence, notifications, live updates |
| User interaction | Major | 2 | Profiles, friends, and basic chat |
| Standard user management and authentication | Major | 2 | Profile editing, avatar, friends, online status |
| ORM | Minor | 1 | Database access and migrations |
| Complete notification system | Minor | 1 | Social and account activity |
| Advanced search | Minor | 1 | Song and user search with filters, sorting, and pagination |
| OAuth 2.0 | Minor | 1 | Additional login method |
| GDPR compliance features | Minor | 1 | Data export and account deletion workflow |
| Prometheus and Grafana | Major | 2 | Metrics, dashboards, alerts, and secured monitoring |

**Candidate validated target: 15 points.**

Possible stretch module:

| Module | Type | Points | Condition |
| --- | --- | ---: | --- |
| Machine-learning recommendation system | Major | 2 | Add only after enough user/list behaviour exists and the team can explain the model |

**Candidate target with stretch: 17 points.** This gives some protection if the stretch module is not ready. It does not protect us if a planned core module fails evaluation, so module acceptance tests must be defined early.

Possible substitute: a secured public API is worth 2 points, but it requires an API key, rate limiting, documentation, and at least five endpoints covering the required HTTP methods.

Important details:

- An avatar upload alone does not satisfy the complete file-upload module.
- A simple similarity formula does not automatically satisfy the machine-learning recommendation module.
- Basic chat is required before claiming advanced chat.
- Only working modules count.

## 4. Proposed technical ownership

Technical ownership gives each person a main area. Everyone still contributes, reviews, tests, and understands the complete project.

| Person | Main area | Proposed responsibility |
| --- | --- | --- |
| Person 1 | Backend / API / architecture | Backend framework, HTTP API structure, shared service patterns, integration decisions |
| Person 2 | Frontend / UX / state | Responsive interface, client state, forms, accessibility, API integration |
| Person 3 — André | Authentication / database / social features | Data model, migrations, authentication rules, profiles, friends, reactions, comments |
| Person 4 | Infrastructure / WebSockets / monitoring | Containers, HTTPS, deployment, real-time transport, Prometheus, Grafana |

### Boundaries that need agreement

- Person 1 owns API architecture; Person 3 owns authentication and social-domain behaviour implemented through that architecture.
- Person 3 defines presence and social-event requirements; Person 4 owns WebSocket transport and connection lifecycle.
- Person 2 owns client behaviour; domain validation must also exist in the backend.
- Database schema changes need review from Person 1 and Person 3.
- Infrastructure changes that affect application configuration need review from the affected owner.

The subject also requires formal roles: Product Owner, Project Manager/Scrum Master, Technical Lead/Architect, and Developers. Technical ownership above does not replace those roles.

## 5. Proposed first milestone

Build one small vertical flow before starting advanced modules:

1. Two users can register and log in securely.
2. Each user can edit a basic profile.
3. Each user can create and reorder one Top 10.
4. One user can send a friend request and the other can accept it.
5. Friends can view each other's Top 10.
6. Data persists after restarting the containers.
7. The complete flow runs through the frontend, backend, and database.

This milestone proves the architecture and team integration. Chat, reactions, external music APIs, recommendations, and monitoring can follow in separate slices.

## 6. Questions every team member should answer

Each person should answer individually. Short answers are enough. **“I don't know” is a valid and useful answer.** It tells us which choices need research, a team decision, or a reversible default.

1. Do you want to build the MyPlaylist idea? Answer **yes**, **no**, or **I don't know**, with one short reason if possible.
2. Which features should definitely be in the first version? Is there anything you would remove or leave for later?
3. Which technical area would you prefer to work on? You can keep the proposed area, request another one, or answer **I don't know**.
4. Do you have a preferred frontend, backend, or database technology? Answer **I don't know** if you have no preference or experience yet.
5. For the database, would you prefer normal PostgreSQL, Supabase, or **I don't know**?
6. Should songs come from an external music service, be added manually, or is this still **I don't know**?
7. Do you agree with the proposed first milestone and module plan? Answer **yes**, **no**, or **I don't know**, and mention one concern if you have one.
8. How much time can you contribute each week, and when can we have a short team meeting?

## 7. Individual response template

Copy this section once per team member.

```markdown
### Name / 42 login

1. MyPlaylist — yes / no / I don't know:
   Reason:
2. First-version features to keep or remove:
3. Preferred technical area / I don't know:
4. Preferred technologies / I don't know:
5. PostgreSQL / Supabase / I don't know:
6. External music service / manual songs / I don't know:
7. First milestone and module plan — yes / no / I don't know:
   Concern:
8. Weekly availability and possible meeting time:

Anything else or another project idea:
```

## 8. Decisions to record after everyone answers

- [ ] Final product concept and name.
- [ ] Core user flow.
- [ ] Features explicitly deferred.
- [ ] Frontend framework.
- [ ] Backend framework.
- [ ] Database platform.
- [ ] Authentication ownership.
- [ ] ORM and migration workflow.
- [ ] Music data source and outage fallback.
- [ ] Real-time architecture.
- [ ] Module list and target points.
- [ ] Technical ownership.
- [ ] Product Owner, Project Manager, and Technical Lead.
- [ ] Task board and communication channel.
- [ ] Review and merge rules.
- [ ] Weekly meeting time.
- [ ] First milestone deadline.

## 9. Definition of a useful team decision

The discussion is complete when every team member has answered, major disagreements are recorded, and the team can explain:

- What the application does.
- Who it serves.
- What belongs in the first milestone.
- Which technologies will be used and why.
- Which modules provide at least 14 validated points.
- Who owns each area and formal role.
- How work, reviews, blockers, and decisions will be tracked.

After agreement, confirmed decisions should replace the draft language in the repository README and implementation plan.
