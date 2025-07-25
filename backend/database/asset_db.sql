PGDMP                      }           asset_db    17.4    17.4 2    �           0    0    ENCODING    ENCODING        SET client_encoding = 'UTF8';
                           false            �           0    0 
   STDSTRINGS 
   STDSTRINGS     (   SET standard_conforming_strings = 'on';
                           false            �           0    0 
   SEARCHPATH 
   SEARCHPATH     8   SELECT pg_catalog.set_config('search_path', '', false);
                           false            �           1262    24580    asset_db    DATABASE     n   CREATE DATABASE asset_db WITH TEMPLATE = template0 ENCODING = 'UTF8' LOCALE_PROVIDER = libc LOCALE = 'en-GB';
    DROP DATABASE asset_db;
                     postgres    false                        3079    24772    pgcrypto 	   EXTENSION     <   CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;
    DROP EXTENSION pgcrypto;
                        false            �           0    0    EXTENSION pgcrypto    COMMENT     <   COMMENT ON EXTENSION pgcrypto IS 'cryptographic functions';
                             false    2            �            1255    24770    generate_udi()    FUNCTION     �   CREATE FUNCTION public.generate_udi() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  IF NEW.udi_code IS NULL THEN
    NEW.udi_code := md5(random()::text || clock_timestamp()::text);
  END IF;
  RETURN NEW;
END;
$$;
 %   DROP FUNCTION public.generate_udi();
       public               postgres    false            �            1259    24597 
   asset_mstr    TABLE     u  CREATE TABLE public.asset_mstr (
    tag_number character varying(100) NOT NULL,
    description character varying(255),
    type_desc character varying(100),
    manufacturer_desc character varying(200),
    model_num character varying(255),
    equ_model_name character varying(100),
    orig_manufacturer_desc character varying(255),
    serial_num character varying(100),
    equ_status_desc character varying(200),
    facility_id character varying(50) NOT NULL,
    client_id character varying(50) NOT NULL,
    udi_code character varying(255) NOT NULL,
    guid character varying(255) DEFAULT (gen_random_uuid())::text
);
    DROP TABLE public.asset_mstr;
       public         heap r       postgres    false            �            1259    24683    assets_id_seq    SEQUENCE     ~   CREATE SEQUENCE public.assets_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    MAXVALUE 2147483647
    CACHE 1;
 $   DROP SEQUENCE public.assets_id_seq;
       public               postgres    false            �            1259    24731    clients    TABLE     v   CREATE TABLE public.clients (
    client_id character varying(50) NOT NULL,
    client_name character varying(255)
);
    DROP TABLE public.clients;
       public         heap r       postgres    false            �            1259    24609    dept    TABLE     {   CREATE TABLE public.dept (
    dept_cd character varying(50) NOT NULL,
    dept_cd_desc character varying(255) NOT NULL
);
    DROP TABLE public.dept;
       public         heap r       postgres    false            �            1259    24619    facility    TABLE       CREATE TABLE public.facility (
    id integer NOT NULL,
    facility_id character varying(50),
    facility_name character varying(255) NOT NULL,
    facility_type character varying(100),
    facility_address character varying(255),
    client_id character varying(50)
);
    DROP TABLE public.facility;
       public         heap r       postgres    false            �            1259    24618    facility_id_seq1    SEQUENCE     �   CREATE SEQUENCE public.facility_id_seq1
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    MAXVALUE 2147483647
    CACHE 1;
 '   DROP SEQUENCE public.facility_id_seq1;
       public               postgres    false    223            �           0    0    facility_id_seq1    SEQUENCE OWNED BY     D   ALTER SEQUENCE public.facility_id_seq1 OWNED BY public.facility.id;
          public               postgres    false    222            �            1259    24756    manager_facilities    TABLE     c   CREATE TABLE public.manager_facilities (
    email text NOT NULL,
    facility_id text NOT NULL
);
 &   DROP TABLE public.manager_facilities;
       public         heap r       postgres    false            �            1259    24830    parts    TABLE        CREATE TABLE public.parts (
    part_name character varying(50) NOT NULL,
    available_quantity integer DEFAULT 0 NOT NULL
);
    DROP TABLE public.parts;
       public         heap r       postgres    false            �            1259    24853    purchase_history    TABLE     �   CREATE TABLE public.purchase_history (
    id integer NOT NULL,
    part_name character varying(50),
    quantity_purchased integer,
    purchase_date timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);
 $   DROP TABLE public.purchase_history;
       public         heap r       postgres    false            �            1259    24852    purchase_history_id_seq    SEQUENCE     �   ALTER TABLE public.purchase_history ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.purchase_history_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);
            public               postgres    false    233            �            1259    24632 
   user_roles    TABLE     �  CREATE TABLE public.user_roles (
    email character varying(255) NOT NULL,
    role character varying(50) NOT NULL,
    facility_id character varying(50),
    assigned_technician character varying(255),
    client_id character varying(50),
    CONSTRAINT user_roles_role_check CHECK (((role)::text = ANY (ARRAY[('director'::character varying)::text, ('manager'::character varying)::text, ('technician'::character varying)::text])))
);
    DROP TABLE public.user_roles;
       public         heap r       postgres    false            �            1259    24585    users    TABLE     �   CREATE TABLE public.users (
    id integer NOT NULL,
    email character varying(255) NOT NULL,
    client_id character varying(50) NOT NULL,
    password character varying(255) NOT NULL
);
    DROP TABLE public.users;
       public         heap r       postgres    false            �            1259    24584    users_id_seq    SEQUENCE     }   CREATE SEQUENCE public.users_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    MAXVALUE 2147483647
    CACHE 1;
 #   DROP SEQUENCE public.users_id_seq;
       public               postgres    false    219            �           0    0    users_id_seq    SEQUENCE OWNED BY     =   ALTER SEQUENCE public.users_id_seq OWNED BY public.users.id;
          public               postgres    false    218            �            1259    24725    wo_priority    TABLE     �   CREATE TABLE public.wo_priority (
    wo_priority_cd character varying(50) NOT NULL,
    wo_priority_cd_desc character varying(255) NOT NULL
);
    DROP TABLE public.wo_priority;
       public         heap r       postgres    false            �            1259    24650    wo_type_code    TABLE     �   CREATE TABLE public.wo_type_code (
    wo_type_cd character varying(50) NOT NULL,
    wo_type_cd_desc character varying(255) NOT NULL
);
     DROP TABLE public.wo_type_code;
       public         heap r       postgres    false            �            1259    24655 
   work_order    TABLE     V  CREATE TABLE public.work_order (
    wo_number character varying(100) NOT NULL,
    wo_description character varying(255),
    wo_type character varying(50),
    wo_priority character varying(50),
    assetnumber character varying(255),
    manufacturername character varying(100),
    modelnumber character varying(255),
    serialnumber character varying(100),
    assignedtodept character varying(50),
    requesteremail character varying(50),
    requestercomments character varying(50),
    datecreated timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    dateavailable date,
    dateneeded date,
    problemcode character varying(50),
    datecompleted date,
    dateupdated timestamp without time zone,
    cc_1 character varying(255),
    cc_2 character varying(255),
    client_id character varying(50) NOT NULL,
    facility_id character varying(255),
    assigned_technician character varying(255),
    parts_needed character varying,
    work_activity_description character varying,
    work_order_status character varying(50) DEFAULT 'Open'::character varying,
    parts_quantity integer
);
    DROP TABLE public.work_order;
       public         heap r       postgres    false            �           2604    24622    facility id    DEFAULT     k   ALTER TABLE ONLY public.facility ALTER COLUMN id SET DEFAULT nextval('public.facility_id_seq1'::regclass);
 :   ALTER TABLE public.facility ALTER COLUMN id DROP DEFAULT;
       public               postgres    false    223    222    223            �           2604    24588    users id    DEFAULT     d   ALTER TABLE ONLY public.users ALTER COLUMN id SET DEFAULT nextval('public.users_id_seq'::regclass);
 7   ALTER TABLE public.users ALTER COLUMN id DROP DEFAULT;
       public               postgres    false    218    219    219            �           2606    24811    asset_mstr asset_mstr_guid_key 
   CONSTRAINT     Y   ALTER TABLE ONLY public.asset_mstr
    ADD CONSTRAINT asset_mstr_guid_key UNIQUE (guid);
 H   ALTER TABLE ONLY public.asset_mstr DROP CONSTRAINT asset_mstr_guid_key;
       public                 postgres    false    220            �           2606    24603    asset_mstr asset_mstr_pkey 
   CONSTRAINT     x   ALTER TABLE ONLY public.asset_mstr
    ADD CONSTRAINT asset_mstr_pkey PRIMARY KEY (tag_number, client_id, facility_id);
 D   ALTER TABLE ONLY public.asset_mstr DROP CONSTRAINT asset_mstr_pkey;
       public                 postgres    false    220    220    220            �           2606    24769 "   asset_mstr asset_mstr_udi_code_key 
   CONSTRAINT     a   ALTER TABLE ONLY public.asset_mstr
    ADD CONSTRAINT asset_mstr_udi_code_key UNIQUE (udi_code);
 L   ALTER TABLE ONLY public.asset_mstr DROP CONSTRAINT asset_mstr_udi_code_key;
       public                 postgres    false    220            �           2606    24735    clients clients_pkey 
   CONSTRAINT     Y   ALTER TABLE ONLY public.clients
    ADD CONSTRAINT clients_pkey PRIMARY KEY (client_id);
 >   ALTER TABLE ONLY public.clients DROP CONSTRAINT clients_pkey;
       public                 postgres    false    229            �           2606    24654    wo_type_code constraint_name 
   CONSTRAINT     b   ALTER TABLE ONLY public.wo_type_code
    ADD CONSTRAINT constraint_name PRIMARY KEY (wo_type_cd);
 F   ALTER TABLE ONLY public.wo_type_code DROP CONSTRAINT constraint_name;
       public                 postgres    false    225            �           2606    24626    facility facility_pkey 
   CONSTRAINT     T   ALTER TABLE ONLY public.facility
    ADD CONSTRAINT facility_pkey PRIMARY KEY (id);
 @   ALTER TABLE ONLY public.facility DROP CONSTRAINT facility_pkey;
       public                 postgres    false    223            �           2606    24762 *   manager_facilities manager_facilities_pkey 
   CONSTRAINT     x   ALTER TABLE ONLY public.manager_facilities
    ADD CONSTRAINT manager_facilities_pkey PRIMARY KEY (email, facility_id);
 T   ALTER TABLE ONLY public.manager_facilities DROP CONSTRAINT manager_facilities_pkey;
       public                 postgres    false    230    230            �           2606    24835    parts parts_pkey 
   CONSTRAINT     U   ALTER TABLE ONLY public.parts
    ADD CONSTRAINT parts_pkey PRIMARY KEY (part_name);
 :   ALTER TABLE ONLY public.parts DROP CONSTRAINT parts_pkey;
       public                 postgres    false    231            �           2606    24613    dept pk_dept_cd 
   CONSTRAINT     R   ALTER TABLE ONLY public.dept
    ADD CONSTRAINT pk_dept_cd PRIMARY KEY (dept_cd);
 9   ALTER TABLE ONLY public.dept DROP CONSTRAINT pk_dept_cd;
       public                 postgres    false    221            �           2606    24729    wo_priority pk_wo_priority_cd 
   CONSTRAINT     g   ALTER TABLE ONLY public.wo_priority
    ADD CONSTRAINT pk_wo_priority_cd PRIMARY KEY (wo_priority_cd);
 G   ALTER TABLE ONLY public.wo_priority DROP CONSTRAINT pk_wo_priority_cd;
       public                 postgres    false    228                        2606    24858 &   purchase_history purchase_history_pkey 
   CONSTRAINT     d   ALTER TABLE ONLY public.purchase_history
    ADD CONSTRAINT purchase_history_pkey PRIMARY KEY (id);
 P   ALTER TABLE ONLY public.purchase_history DROP CONSTRAINT purchase_history_pkey;
       public                 postgres    false    233            �           2606    24639    user_roles user_roles_pkey 
   CONSTRAINT     [   ALTER TABLE ONLY public.user_roles
    ADD CONSTRAINT user_roles_pkey PRIMARY KEY (email);
 D   ALTER TABLE ONLY public.user_roles DROP CONSTRAINT user_roles_pkey;
       public                 postgres    false    224            �           2606    24596    users users_email_key 
   CONSTRAINT     Q   ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);
 ?   ALTER TABLE ONLY public.users DROP CONSTRAINT users_email_key;
       public                 postgres    false    219            �           2606    24592    users users_pkey 
   CONSTRAINT     N   ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);
 :   ALTER TABLE ONLY public.users DROP CONSTRAINT users_pkey;
       public                 postgres    false    219            �           2606    24662    work_order wo_order_pkey 
   CONSTRAINT     h   ALTER TABLE ONLY public.work_order
    ADD CONSTRAINT wo_order_pkey PRIMARY KEY (wo_number, client_id);
 B   ALTER TABLE ONLY public.work_order DROP CONSTRAINT wo_order_pkey;
       public                 postgres    false    226    226                       2620    24771    asset_mstr trg_generate_udi    TRIGGER     x   CREATE TRIGGER trg_generate_udi BEFORE INSERT ON public.asset_mstr FOR EACH ROW EXECUTE FUNCTION public.generate_udi();
 4   DROP TRIGGER trg_generate_udi ON public.asset_mstr;
       public               postgres    false    220    234                       2606    24741    asset_mstr asset_client_fk    FK CONSTRAINT     �   ALTER TABLE ONLY public.asset_mstr
    ADD CONSTRAINT asset_client_fk FOREIGN KEY (client_id) REFERENCES public.clients(client_id);
 D   ALTER TABLE ONLY public.asset_mstr DROP CONSTRAINT asset_client_fk;
       public               postgres    false    4858    220    229                       2606    24746    facility facility_client_fk    FK CONSTRAINT     �   ALTER TABLE ONLY public.facility
    ADD CONSTRAINT facility_client_fk FOREIGN KEY (client_id) REFERENCES public.clients(client_id);
 E   ALTER TABLE ONLY public.facility DROP CONSTRAINT facility_client_fk;
       public               postgres    false    223    229    4858                       2606    24763 0   manager_facilities manager_facilities_email_fkey    FK CONSTRAINT     �   ALTER TABLE ONLY public.manager_facilities
    ADD CONSTRAINT manager_facilities_email_fkey FOREIGN KEY (email) REFERENCES public.user_roles(email);
 Z   ALTER TABLE ONLY public.manager_facilities DROP CONSTRAINT manager_facilities_email_fkey;
       public               postgres    false    230    4850    224                       2606    24640     user_roles user_roles_email_fkey    FK CONSTRAINT     �   ALTER TABLE ONLY public.user_roles
    ADD CONSTRAINT user_roles_email_fkey FOREIGN KEY (email) REFERENCES public.users(email);
 J   ALTER TABLE ONLY public.user_roles DROP CONSTRAINT user_roles_email_fkey;
       public               postgres    false    4836    224    219                       2606    24736    users users_client_fk    FK CONSTRAINT        ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_client_fk FOREIGN KEY (client_id) REFERENCES public.clients(client_id);
 ?   ALTER TABLE ONLY public.users DROP CONSTRAINT users_client_fk;
       public               postgres    false    4858    219    229                       2606    24678    work_order wo_type_fkey    FK CONSTRAINT     �   ALTER TABLE ONLY public.work_order
    ADD CONSTRAINT wo_type_fkey FOREIGN KEY (wo_type) REFERENCES public.wo_type_code(wo_type_cd);
 A   ALTER TABLE ONLY public.work_order DROP CONSTRAINT wo_type_fkey;
       public               postgres    false    4852    226    225                       2606    24751    work_order workorder_client_fk    FK CONSTRAINT     �   ALTER TABLE ONLY public.work_order
    ADD CONSTRAINT workorder_client_fk FOREIGN KEY (client_id) REFERENCES public.clients(client_id);
 H   ALTER TABLE ONLY public.work_order DROP CONSTRAINT workorder_client_fk;
       public               postgres    false    4858    229    226           