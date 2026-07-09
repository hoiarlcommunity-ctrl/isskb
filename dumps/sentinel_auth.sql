--
-- PostgreSQL database dump
--

\restrict 1ge2yqS1wY3wn7mvfb3FNi2KRgJ9SzCaU4zUKtBpCMQNQVEx0u9O2ix04qDtOh0

-- Dumped from database version 16.14
-- Dumped by pg_dump version 16.14

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: auth_audit; Type: TABLE; Schema: public; Owner: sentinel_user
--

CREATE TABLE public.auth_audit (
    id integer NOT NULL,
    user_id integer,
    username character varying(100),
    action character varying(50) NOT NULL,
    ip_address character varying(45),
    user_agent text,
    success boolean NOT NULL,
    detail text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.auth_audit OWNER TO sentinel_user;

--
-- Name: auth_audit_id_seq; Type: SEQUENCE; Schema: public; Owner: sentinel_user
--

CREATE SEQUENCE public.auth_audit_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.auth_audit_id_seq OWNER TO sentinel_user;

--
-- Name: auth_audit_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: sentinel_user
--

ALTER SEQUENCE public.auth_audit_id_seq OWNED BY public.auth_audit.id;


--
-- Name: refresh_tokens; Type: TABLE; Schema: public; Owner: sentinel_user
--

CREATE TABLE public.refresh_tokens (
    id integer NOT NULL,
    user_id integer NOT NULL,
    token_hash character varying(64) NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    revoked boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.refresh_tokens OWNER TO sentinel_user;

--
-- Name: refresh_tokens_id_seq; Type: SEQUENCE; Schema: public; Owner: sentinel_user
--

CREATE SEQUENCE public.refresh_tokens_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.refresh_tokens_id_seq OWNER TO sentinel_user;

--
-- Name: refresh_tokens_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: sentinel_user
--

ALTER SEQUENCE public.refresh_tokens_id_seq OWNED BY public.refresh_tokens.id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: sentinel_user
--

CREATE TABLE public.users (
    id integer NOT NULL,
    username character varying(100) NOT NULL,
    password_hash character varying(255) NOT NULL,
    full_name character varying(200),
    role character varying(50) DEFAULT 'operator'::character varying NOT NULL,
    office_id character varying(50) DEFAULT 'main'::character varying NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    failed_attempts integer DEFAULT 0 NOT NULL,
    locked_until timestamp with time zone,
    last_login timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    job_title character varying(200),
    phone character varying(50),
    notes text,
    phone_work character varying(9)
);


ALTER TABLE public.users OWNER TO sentinel_user;

--
-- Name: users_id_seq; Type: SEQUENCE; Schema: public; Owner: sentinel_user
--

CREATE SEQUENCE public.users_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.users_id_seq OWNER TO sentinel_user;

--
-- Name: users_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: sentinel_user
--

ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;


--
-- Name: auth_audit id; Type: DEFAULT; Schema: public; Owner: sentinel_user
--

ALTER TABLE ONLY public.auth_audit ALTER COLUMN id SET DEFAULT nextval('public.auth_audit_id_seq'::regclass);


--
-- Name: refresh_tokens id; Type: DEFAULT; Schema: public; Owner: sentinel_user
--

ALTER TABLE ONLY public.refresh_tokens ALTER COLUMN id SET DEFAULT nextval('public.refresh_tokens_id_seq'::regclass);


--
-- Name: users id; Type: DEFAULT; Schema: public; Owner: sentinel_user
--

ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);


--
-- Data for Name: auth_audit; Type: TABLE DATA; Schema: public; Owner: sentinel_user
--

COPY public.auth_audit (id, user_id, username, action, ip_address, user_agent, success, detail, created_at) FROM stdin;
1	1	admin	login_ok	127.0.0.1	Mozilla/5.0 (Windows NT; Windows NT 10.0; ru-RU) WindowsPowerShell/5.1.26100.8655	t		2026-06-24 12:43:27.425793+00
2	1	admin	login_ok	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-24 12:51:37.267711+00
3	1	admin	logout	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-24 12:52:06.968681+00
4	1	OD_12GU	login_fail	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	f	wrong password, attempt 1	2026-06-24 13:11:43.375902+00
5	1	OD_12GU	login_ok	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-24 13:12:08.719804+00
6	1	OD_12GU	logout	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-24 13:12:19.570029+00
7	1	OD_12GU	login_ok	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-24 13:12:33.609799+00
8	1	OD_12GU	logout	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-24 13:13:42.737454+00
9	1	OD_12GU	login_ok	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-24 13:16:15.817557+00
10	1	OD_12GU	logout	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-24 13:16:21.853129+00
11	1	OD_12GU	login_ok	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-24 13:29:52.059735+00
12	1	OD_12GU	logout	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-24 13:34:53.155521+00
13	1	OD_12GU	login_ok	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-24 13:36:21.691501+00
14	1	OD_12GU	logout	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-24 13:36:39.664232+00
15	1	OD_12GU	login_ok	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-24 13:37:10.953258+00
16	1	OD_12GU	logout	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-24 13:38:37.637824+00
17	1	OD_12GU	login_ok	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-24 20:10:41.380713+00
18	1	OD_12GU	logout	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-24 20:13:18.41942+00
19	1	OD_12GU	login_ok	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-24 20:18:33.974053+00
20	1	OD_12GU	logout	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-24 20:22:20.023294+00
21	1	OD_12GU	login_ok	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-24 20:35:51.124404+00
22	1	OD_12GU	logout	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-24 20:37:41.235884+00
23	1	OD_12GU	login_fail	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	f	wrong password, attempt 1	2026-06-24 20:43:37.010054+00
24	1	OD_12GU	login_ok	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-24 20:43:46.143946+00
25	1	OD_12GU	login_ok	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-24 22:55:34.335154+00
26	1	OD_12GU	logout	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-24 23:04:32.231339+00
27	1	OD_12GU	login_ok	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-24 23:04:44.86381+00
28	1	OD_12GU	login_ok	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-25 08:04:06.528158+00
29	1	OD_12GU	login_fail	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	f	wrong password, attempt 1	2026-06-25 19:48:30.68933+00
30	1	OD_12GU	login_ok	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-25 19:48:40.867768+00
31	1	OD_12GU	logout	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-25 19:50:00.81488+00
32	\N	admin	login_fail	127.0.0.1	Mozilla/5.0 (Windows NT; Windows NT 10.0; ru-RU) WindowsPowerShell/5.1.26100.8655	f	user not found	2026-06-26 05:10:09.38339+00
33	\N	admin	login_fail	127.0.0.1	Mozilla/5.0 (Windows NT; Windows NT 10.0; ru-RU) WindowsPowerShell/5.1.26100.8655	f	user not found	2026-06-26 05:11:31.079913+00
34	1	OD_12GU	login_ok	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-26 05:15:14.453439+00
35	1	OD_12GU	login_ok	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-26 05:19:23.723811+00
36	1	OD_12GU	login_ok	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-26 05:33:21.427043+00
37	1	OD_12GU	login_ok	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-26 06:53:20.791927+00
38	1	OD_12GU	login_ok	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-26 07:59:58.168623+00
39	1	OD_12GU	login_ok	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-26 08:33:56.832049+00
40	1	OD_12GU	logout	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-26 08:35:13.812713+00
41	1	OD_12GU	login_ok	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-26 08:36:01.732652+00
42	1	OD_12GU	logout	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-26 08:37:58.239438+00
43	1	OD_12GU	login_ok	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-26 08:38:17.058074+00
44	1	OD_12GU	login_ok	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-26 11:09:05.990581+00
45	1	OD_12GU	logout	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-26 11:19:54.835804+00
46	\N	admin	login_fail	127.0.0.1	Mozilla/5.0 (Windows NT; Windows NT 10.0; ru-RU) WindowsPowerShell/5.1.26100.8655	f	user not found	2026-06-26 11:54:56.069755+00
47	1	OD_12GU	login_ok	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-26 11:56:49.01929+00
48	1	OD_12GU	login_ok	127.0.0.1	Mozilla/5.0 (Windows NT; Windows NT 10.0; ru-RU) WindowsPowerShell/5.1.26100.8655	t		2026-06-26 12:28:44.263982+00
49	1	OD_12GU	login_ok	127.0.0.1	Mozilla/5.0 (Windows NT; Windows NT 10.0; ru-RU) WindowsPowerShell/5.1.26100.8655	t		2026-06-26 12:29:33.829395+00
50	1	OD_12GU	login_ok	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-26 12:35:21.439792+00
51	1	OD_12GU	login_ok	127.0.0.1	Mozilla/5.0 (Windows NT; Windows NT 10.0; ru-RU) WindowsPowerShell/5.1.26100.8655	t		2026-06-26 13:10:36.185488+00
52	1	OD_12GU	login_ok	127.0.0.1	Mozilla/5.0 (Windows NT; Windows NT 10.0; ru-RU) WindowsPowerShell/5.1.26100.8655	t		2026-06-26 13:13:11.304839+00
53	1	OD_12GU	login_ok	127.0.0.1	Mozilla/5.0 (Windows NT; Windows NT 10.0; ru-RU) WindowsPowerShell/5.1.26100.8655	t		2026-06-26 13:18:16.083606+00
54	1	OD_12GU	login_ok	127.0.0.1	Mozilla/5.0 (Windows NT; Windows NT 10.0; ru-RU) WindowsPowerShell/5.1.26100.8655	t		2026-06-26 13:28:45.574866+00
55	1	OD_12GU	login_ok	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-26 13:32:30.437819+00
56	1	OD_12GU	logout	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-26 13:35:45.86965+00
57	1	OD_12GU	login_ok	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-26 13:35:54.437833+00
58	1	OD_12GU	login_ok	127.0.0.1	Mozilla/5.0 (Windows NT; Windows NT 10.0; ru-RU) WindowsPowerShell/5.1.26100.8655	t		2026-06-26 13:50:12.150367+00
59	1	OD_12GU	login_ok	127.0.0.1	Mozilla/5.0 (Windows NT; Windows NT 10.0; ru-RU) WindowsPowerShell/5.1.26100.8655	t		2026-06-26 13:50:24.110593+00
60	1	OD_12GU	login_ok	127.0.0.1	Mozilla/5.0 (Windows NT; Windows NT 10.0; ru-RU) WindowsPowerShell/5.1.26100.8655	t		2026-06-26 13:51:03.210329+00
61	1	OD_12GU	login_ok	127.0.0.1	Mozilla/5.0 (Windows NT; Windows NT 10.0; ru-RU) WindowsPowerShell/5.1.26100.8655	t		2026-06-26 13:51:36.571736+00
62	1	OD_12GU	login_ok	127.0.0.1	Mozilla/5.0 (Windows NT; Windows NT 10.0; ru-RU) WindowsPowerShell/5.1.26100.8655	t		2026-06-26 13:51:52.262681+00
63	1	OD_12GU	login_ok	127.0.0.1	Mozilla/5.0 (Windows NT; Windows NT 10.0; ru-RU) WindowsPowerShell/5.1.26100.8655	t		2026-06-26 13:52:13.652945+00
64	1	OD_12GU	login_ok	127.0.0.1	Mozilla/5.0 (Windows NT; Windows NT 10.0; ru-RU) WindowsPowerShell/5.1.26100.8655	t		2026-06-26 13:52:33.327206+00
65	1	OD_12GU	login_ok	127.0.0.1	Mozilla/5.0 (Windows NT; Windows NT 10.0; ru-RU) WindowsPowerShell/5.1.26100.8655	t		2026-06-26 13:52:49.898834+00
66	1	OD_12GU	login_ok	127.0.0.1	Mozilla/5.0 (Windows NT; Windows NT 10.0; ru-RU) WindowsPowerShell/5.1.26100.8655	t		2026-06-26 13:57:00.516263+00
67	1	OD_12GU	login_ok	127.0.0.1	Mozilla/5.0 (Windows NT; Windows NT 10.0; ru-RU) WindowsPowerShell/5.1.26100.8655	t		2026-06-26 13:57:17.848034+00
68	1	OD_12GU	login_ok	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-26 13:58:40.417249+00
69	1	OD_12GU	logout	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-26 14:00:07.855587+00
70	1	OD_12GU	login_ok	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-26 14:00:19.282321+00
71	1	OD_12GU	logout	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-26 14:07:05.112884+00
72	1	OD_12GU	login_ok	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-26 14:07:35.643045+00
73	1	OD_12GU	logout	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-26 14:07:46.135538+00
74	1	OD_12GU	login_ok	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-26 14:07:53.205757+00
75	1	OD_12GU	logout	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-26 14:32:41.786205+00
76	1	OD_12GU	login_ok	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-26 14:33:01.602009+00
77	1	OD_12GU	login_ok	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-26 14:39:07.327123+00
78	1	OD_12GU	logout	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-26 14:39:26.618048+00
110	1	OD_12GU	login_ok	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-26 14:52:05.244036+00
111	1	OD_12GU	login_ok	127.0.0.1	Mozilla/5.0 (Windows NT; Windows NT 10.0; ru-RU) WindowsPowerShell/5.1.26100.8655	t		2026-06-26 15:18:27.224061+00
112	1	OD_12GU	login_ok	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-26 15:19:30.484939+00
113	1	OD_12GU	logout	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-26 15:41:56.419857+00
114	1	OD_12GU	login_fail	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	f	wrong password, attempt 1	2026-06-26 15:42:03.196365+00
115	1	OD_12GU	login_ok	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-26 15:42:08.414298+00
116	1	OD_12GU	login_ok	127.0.0.1	Mozilla/5.0 (Windows NT; Windows NT 10.0; ru-RU) WindowsPowerShell/5.1.26100.8655	t		2026-06-26 16:22:19.986232+00
117	1	OD_12GU	login_ok	127.0.0.1	Mozilla/5.0 (Windows NT; Windows NT 10.0; ru-RU) WindowsPowerShell/5.1.26100.8655	t		2026-06-26 16:22:32.460834+00
118	1	OD_12GU	login_ok	127.0.0.1	Mozilla/5.0 (Windows NT; Windows NT 10.0; ru-RU) WindowsPowerShell/5.1.26100.8655	t		2026-06-26 16:23:15.565051+00
119	1	OD_12GU	login_ok	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-26 16:24:36.492657+00
120	1	OD_12GU	login_ok	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-27 06:26:10.667519+00
121	1	OD_12GU	login_ok	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-27 06:37:07.333921+00
122	1	OD_12GU	login_ok	192.168.1.100	Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:152.0) Gecko/20100101 Firefox/152.0	t		2026-06-27 06:40:08.950506+00
123	1	OD_12GU	login_ok	192.168.1.90	Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:152.0) Gecko/20100101 Firefox/152.0	t		2026-06-27 06:49:47.982958+00
124	1	OD_12GU	login_ok	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-28 10:14:23.256838+00
125	1	OD_12GU	login_ok	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-30 20:54:56.969025+00
126	1	OD_12GU	logout	127.0.0.1	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	t		2026-06-30 21:02:19.21684+00
\.


--
-- Data for Name: refresh_tokens; Type: TABLE DATA; Schema: public; Owner: sentinel_user
--

COPY public.refresh_tokens (id, user_id, token_hash, expires_at, revoked, created_at) FROM stdin;
92	1	020389ab0412ac8cd5c2cbb2fe35bbdcf8844af8edeb9820a4be0706557c9a89	2026-07-04 06:26:10.652351+00	t	2026-06-27 06:26:10.66044+00
93	1	61bed646f67757d19f3ed0c5fa0229ea0e5f29c680a6d4d4d2a4125e6e998b76	2026-07-04 06:37:07.31795+00	t	2026-06-27 06:37:07.326295+00
94	1	eed793671c1d9a7d4a8208973f0ebb1084eb2b8fe9ec3f441d62633cc91c0dfc	2026-07-04 06:40:08.944624+00	t	2026-06-27 06:40:08.946877+00
96	1	f2c779f987110bd331feaa95756124dede62600eae67273a9f4372a1ee7e298d	2026-07-05 10:14:23.235581+00	t	2026-06-28 10:14:23.246356+00
97	1	ab40b81b95a33c854623e12e2d2eb27220335e1270aaf5927ea1cb4fb36698dc	2026-07-07 20:54:56.941853+00	t	2026-06-30 20:54:56.959652+00
33	1	d24dc0d4725c308ab26982d5dd75e0d226984dfabba6477c9af1dd7eb9bfe6c7	2026-07-03 13:28:45.55931+00	t	2026-06-26 13:28:45.566798+00
34	1	03c1a55a3aaec6b9abb835b6910d126ad1c8aca119deb04532f46fc6133a1b08	2026-07-03 13:32:30.425856+00	t	2026-06-26 13:32:30.430894+00
11	1	fe19dcbcf76526d939d24ed37350c2c7a52057701f3725bd41d618ab1b174fcf	2026-07-01 20:35:51.118431+00	t	2026-06-24 20:35:51.120238+00
1	1	9d402887e4157ee9996c2cf0f84bd1a93b0edd2d4691afd78333756b6e496001	2026-07-01 12:43:27.418698+00	t	2026-06-24 12:43:27.421112+00
2	1	d7fb9f9794b1810804c839cb48bb8c3f0584184dd9bc6dc4ce99f1b1001876e0	2026-07-01 12:51:37.25795+00	t	2026-06-24 12:51:37.262969+00
3	1	db1b183429cc687f6dc4e532bcc093b0a74dba725899c9741054679bdc23713d	2026-07-01 13:12:08.713435+00	t	2026-06-24 13:12:08.715751+00
4	1	ed17b34c9b874e44de6b2d8c65f9833f293e3fdcdc6f108769a1f1800705de3f	2026-07-01 13:12:33.606032+00	t	2026-06-24 13:12:33.606463+00
5	1	729383321ca7ac62160d118917155525e3961116a84865efa496788813ff5ef9	2026-07-01 13:16:15.812728+00	t	2026-06-24 13:16:15.814135+00
6	1	564d725aa29a6d3e192ea321baef14d0b477357efa580dac2388489263bd2220	2026-07-01 13:29:52.048698+00	t	2026-06-24 13:29:52.053119+00
49	1	81b757b6d4705c59df6c2d932b76146352f53a0e57872f998206b2812d29129c	2026-07-03 14:07:53.201154+00	t	2026-06-26 14:07:53.201072+00
51	1	a90d10842c0fa15045b8ecf19cd46023a18c4d7f3f0df04a91cf2270b3cb9f0e	2026-07-03 14:39:07.314495+00	t	2026-06-26 14:39:07.32057+00
84	1	d2635641cece77bfdeb7c55a6fe47214d726cc60f7603ee0758d1a4f05cf3cde	2026-07-03 14:52:05.22514+00	t	2026-06-26 14:52:05.233712+00
25	1	0ff94e7081608c5c97e0ecac2fd7cc2f6038d8feb5823464427b36d319672c51	2026-07-03 11:09:05.964308+00	t	2026-06-26 11:09:05.978453+00
27	1	5ebfdd0b781bb40337c5620a3f6e028e65008e1ff9d66c18643946b3552392e5	2026-07-03 12:28:44.252032+00	t	2026-06-26 12:28:44.258041+00
28	1	a7628717fdc1e72707fcecc339bae3967284c349390116c191ad0619f3ce4ca4	2026-07-03 12:29:33.818226+00	t	2026-06-26 12:29:33.824632+00
30	1	f8ddcb1b18cd50f2579ae9d0af4b11dc25000cbc67568b2a86737e5014fc3c45	2026-07-03 13:10:36.173616+00	t	2026-06-26 13:10:36.17916+00
31	1	013600da19016a496496cee631215c9f3100dfac96b15daf0915f8a53a529d00	2026-07-03 13:13:11.293851+00	t	2026-06-26 13:13:11.298126+00
35	1	000dcbf9f3e7eda32c40e01dc6165e1c974336ec661359772deb3493caaa6663	2026-07-03 13:35:54.428949+00	t	2026-06-26 13:35:54.430642+00
95	1	5801b961f43a8735375978e50269638597c5b8c29daf943f0bd79cdb48d6fa16	2026-07-04 06:49:47.975438+00	t	2026-06-27 06:49:47.978601+00
32	1	389d2b63fd52fe4b4f62456fec3cef3b392b2d3c67f28c5159a69828f206727a	2026-07-03 13:18:16.072178+00	t	2026-06-26 13:18:16.077973+00
47	1	5f5fefadf043aff1b16c2e663403c28743c15be5d3e3fac4ffdc2b1ab6d63b60	2026-07-03 14:00:19.273823+00	t	2026-06-26 14:00:19.275535+00
13	1	a8b3069eed8da1a9ef20fe0595bc7a40e947f92668d97ceb8cf83d250bdb1bc9	2026-07-01 22:55:34.312784+00	t	2026-06-24 22:55:34.323583+00
15	1	be2e5b1fe6a1c3b3a7b08671d711c0701b87cc600b6b4fe9cdb257bcf43182bf	2026-07-02 08:04:06.514871+00	t	2026-06-25 08:04:06.521247+00
16	1	bcd5f8aea6ec5cba77da4a5604b3792a891ed6b776531b2bb565b621b5326f25	2026-07-02 19:48:40.853182+00	t	2026-06-25 19:48:40.860745+00
17	1	6a076daf81348b2498665d500d61ebe555cc47513c84df6cd073eaff15c3b618	2026-07-03 05:15:14.433959+00	t	2026-06-26 05:15:14.444063+00
7	1	23bc327dd6dfa78060b06dec239bc93e39ec4c33d347730bf2217a0ad7e6fa44	2026-07-01 13:36:21.681034+00	t	2026-06-24 13:36:21.683961+00
8	1	c7bcf975450acbd660181b6a094281daabef39945cfc55b893f3e9a4c789fa42	2026-07-01 13:37:10.945895+00	t	2026-06-24 13:37:10.947068+00
9	1	3bab9eb9c374e01be947d418e4810974799369e588c22f3891cecc963117defc	2026-07-01 20:10:41.369724+00	t	2026-06-24 20:10:41.374321+00
10	1	064e4eed8c767a4d137ccbf9b765ecc17851d45e6035e3d0b6216cd13c062299	2026-07-01 20:18:33.96803+00	t	2026-06-24 20:18:33.969541+00
12	1	199cb6e9850a91952a9d415b4f97f3562b75608c4cbaa940fda6394505441a9d	2026-07-01 20:43:46.136915+00	t	2026-06-24 20:43:46.13977+00
14	1	bae8c4bd77ccdc3c25eb2867de6133fd30d10a9e7a9dc4e7020563214c471d98	2026-07-01 23:04:44.85299+00	t	2026-06-24 23:04:44.856314+00
21	1	b703e5126d189f10ae284ee9f4cd7369ef4ac2d4d811e32a122fbaefbfe70ca2	2026-07-03 07:59:58.156738+00	t	2026-06-26 07:59:58.162064+00
23	1	cf7dd6e3637eb168ae007046e103e6335c404c2fffa4ea4b4a25b92b52e3921d	2026-07-03 08:36:01.724369+00	t	2026-06-26 08:36:01.726319+00
24	1	aa4ba4b0c103340aa5c47dfa7174b55de1aaeb47363d7252b2d53adebbbdfb1b	2026-07-03 08:38:17.051946+00	t	2026-06-26 08:38:17.053249+00
50	1	22260839d9307d63a4667a0d31ed2479921f054d893e258b3f0072ede57776fd	2026-07-03 14:33:01.59403+00	t	2026-06-26 14:33:01.596207+00
26	1	f012fd4f3d7e601383b4b204c7069bca09254ee56516f1020013e79dd4fe6c85	2026-07-03 11:56:49.0098+00	t	2026-06-26 11:56:49.013372+00
29	1	2c141e466a5818113e4447ec42fcd573a9225a774b16907cd763968ee268eda5	2026-07-03 12:35:21.42639+00	t	2026-06-26 12:35:21.43271+00
18	1	f725b212279a02512287398b033b8acbd29729efa6cb86f2dcd0787fe25eb21f	2026-07-03 05:19:23.706948+00	t	2026-06-26 05:19:23.713267+00
19	1	a61a716433f251a1d87ab70b0cdf6c186dcdeefdf6bba9274573d502f664a644	2026-07-03 05:33:11.036619+00	t	2026-06-26 05:33:11.087701+00
20	1	da382246aa9727a9d72e70fdb511c881e367324d840597c7d57d96b76310136e	2026-07-03 06:53:20.778939+00	t	2026-06-26 06:53:20.785182+00
22	1	37296e6a895120566cf5f363c2fb7147c9847e791628f7f4d3830181a03817c5	2026-07-03 08:33:56.820753+00	t	2026-06-26 08:33:56.826083+00
44	1	ca1af79a1554e20f38259879006258559050449899a1cd437ad2901d4d08d15f	2026-07-03 13:57:00.504911+00	t	2026-06-26 13:57:00.510442+00
45	1	a3400d82da169a86356f76e2ffd323ed7de13caaa70ede492b79167578dcde81	2026-07-03 13:57:17.837666+00	t	2026-06-26 13:57:17.842932+00
46	1	87ed0ee772ea67a58a536d84d09e1f72616c1a15893166736472ddb44bb3ac20	2026-07-03 13:58:40.407922+00	t	2026-06-26 13:58:40.412554+00
36	1	bee9d4690617afb979afda04fac769c1b497cd2f0c6313895316577c5090acb5	2026-07-03 13:50:12.138414+00	t	2026-06-26 13:50:12.144385+00
37	1	8b1886d331edb4c71c29a6576fb1aadae7c2b5233c4690e133f38937f490bd27	2026-07-03 13:50:24.100015+00	t	2026-06-26 13:50:24.104505+00
38	1	d06b0bfa7bdffa46b66767ec455b1d1e5d11398c17ebdb9b0929892666ade4be	2026-07-03 13:51:03.197848+00	t	2026-06-26 13:51:03.203216+00
39	1	3b376a838e3d3f61dd8a2568a9bb8a567593dd81416e2236604c2464664b43f8	2026-07-03 13:51:36.562649+00	t	2026-06-26 13:51:36.567077+00
40	1	9d8f29313353ebd9b07fc88c827689d61990d2704fcd9c6c76d14c29fe114b0b	2026-07-03 13:51:52.253859+00	t	2026-06-26 13:51:52.257948+00
41	1	c058de646bb687f98828526af343f869fa4998597409f9559fa72634fbfacd16	2026-07-03 13:52:13.643313+00	t	2026-06-26 13:52:13.64854+00
42	1	92d1fc29180a312bc5162f9760bb667e5339493c023bd5bad27e9c1dcccf461e	2026-07-03 13:52:33.318409+00	t	2026-06-26 13:52:33.322321+00
43	1	2d6562edbbb3291b36adef7a3fe6841e1f9177b2d34dc0586c13a4a0c14d5a9e	2026-07-03 13:52:49.885501+00	t	2026-06-26 13:52:49.892041+00
48	1	97a61a7e2ea597571f4583bfe0a103df45664de5689e8d0d4294aaf566022f70	2026-07-03 14:07:35.635308+00	t	2026-06-26 14:07:35.637061+00
85	1	097aea90a8ebce06abcbd9f03cf8cf949b454822a9748c3feef81fe14181079e	2026-07-03 15:18:27.199615+00	t	2026-06-26 15:18:27.212161+00
86	1	2caa34bd95da42a2cee0d44e2f4fc38bce78a1587ca182f7198730614446ac23	2026-07-03 15:19:30.472792+00	t	2026-06-26 15:19:30.47857+00
87	1	73b10b5c442e749cd386d614cc9ae5caf9aaf463c7beb305c0aa1747a06f20f7	2026-07-03 15:42:08.401681+00	t	2026-06-26 15:42:08.405913+00
88	1	6616c4f6e784a52dc3fbed4f63ce0bea81c57f1d309374192f58d52d8dcf32a7	2026-07-03 16:22:19.974099+00	t	2026-06-26 16:22:19.980108+00
89	1	53244827cf68e01e5d37e2e21c1026ca82ad79750f78edffa38f7344bbed1cb5	2026-07-03 16:22:32.451428+00	t	2026-06-26 16:22:32.456175+00
90	1	f6d514f08175ad99d90f0e52badea723efa07b4507c66ec02af786c227309b3c	2026-07-03 16:23:15.556285+00	t	2026-06-26 16:23:15.560279+00
91	1	cf7e33897c0c89f4f39a5e48f4264a5964736556ce4ba29003f3e3d3081b941f	2026-07-03 16:24:36.482856+00	t	2026-06-26 16:24:36.48806+00
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: sentinel_user
--

COPY public.users (id, username, password_hash, full_name, role, office_id, is_active, failed_attempts, locked_until, last_login, created_at, updated_at, job_title, phone, notes, phone_work) FROM stdin;
1	OD_12GU	$2b$12$99o2eB2ih/Nue1LQUy4At.pmQkoVA54bSSS4wcHdTlLOCinRAg1tq	ОД 12 ГУ	admin	12GU	t	0	\N	2026-06-30 20:54:56.923736+00	2026-06-24 12:38:23.787874+00	2026-06-26 14:24:08.862434+00	Оперативный дежурный	79533333333	\N	111111111
\.


--
-- Name: auth_audit_id_seq; Type: SEQUENCE SET; Schema: public; Owner: sentinel_user
--

SELECT pg_catalog.setval('public.auth_audit_id_seq', 126, true);


--
-- Name: refresh_tokens_id_seq; Type: SEQUENCE SET; Schema: public; Owner: sentinel_user
--

SELECT pg_catalog.setval('public.refresh_tokens_id_seq', 97, true);


--
-- Name: users_id_seq; Type: SEQUENCE SET; Schema: public; Owner: sentinel_user
--

SELECT pg_catalog.setval('public.users_id_seq', 2, true);


--
-- Name: auth_audit auth_audit_pkey; Type: CONSTRAINT; Schema: public; Owner: sentinel_user
--

ALTER TABLE ONLY public.auth_audit
    ADD CONSTRAINT auth_audit_pkey PRIMARY KEY (id);


--
-- Name: refresh_tokens refresh_tokens_pkey; Type: CONSTRAINT; Schema: public; Owner: sentinel_user
--

ALTER TABLE ONLY public.refresh_tokens
    ADD CONSTRAINT refresh_tokens_pkey PRIMARY KEY (id);


--
-- Name: refresh_tokens refresh_tokens_token_hash_key; Type: CONSTRAINT; Schema: public; Owner: sentinel_user
--

ALTER TABLE ONLY public.refresh_tokens
    ADD CONSTRAINT refresh_tokens_token_hash_key UNIQUE (token_hash);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: sentinel_user
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: users users_username_key; Type: CONSTRAINT; Schema: public; Owner: sentinel_user
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_username_key UNIQUE (username);


--
-- Name: idx_audit_ts; Type: INDEX; Schema: public; Owner: sentinel_user
--

CREATE INDEX idx_audit_ts ON public.auth_audit USING btree (created_at DESC);


--
-- Name: idx_audit_user; Type: INDEX; Schema: public; Owner: sentinel_user
--

CREATE INDEX idx_audit_user ON public.auth_audit USING btree (user_id);


--
-- Name: idx_rt_hash; Type: INDEX; Schema: public; Owner: sentinel_user
--

CREATE INDEX idx_rt_hash ON public.refresh_tokens USING btree (token_hash);


--
-- Name: idx_rt_user_id; Type: INDEX; Schema: public; Owner: sentinel_user
--

CREATE INDEX idx_rt_user_id ON public.refresh_tokens USING btree (user_id);


--
-- Name: auth_audit auth_audit_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: sentinel_user
--

ALTER TABLE ONLY public.auth_audit
    ADD CONSTRAINT auth_audit_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- Name: refresh_tokens refresh_tokens_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: sentinel_user
--

ALTER TABLE ONLY public.refresh_tokens
    ADD CONSTRAINT refresh_tokens_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict 1ge2yqS1wY3wn7mvfb3FNi2KRgJ9SzCaU4zUKtBpCMQNQVEx0u9O2ix04qDtOh0

