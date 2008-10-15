CREATE TABLE Elements (
  id TEXT PRIMARY KEY
);

CREATE TABLE Meta (
  element TEXT NOT NULL,
  key     TEXT NOT NULL,
  value   TEXT NOT NULL,
  PRIMARY KEY (element, key),
  FOREIGN KEY (element) references Elements (id)
  -- package metadata use an empty string in column element
);

CREATE TABLE Contents (
  element  TEXT PRIMARY KEY,
  mimetype TEXT NOT NULL,
  schema   TEXT,
  data     BLOB,
  url      TEXT,
  FOREIGN KEY (element) references Elements  (id)
  -- only elements with a content should be referenced by element
  -- if not null, schema must be a path identifying an own or imported resource
  -- exactly one of content and url must be not null
);

CREATE TABLE Streams (
  id  TEXT PRIMARY KEY,
  url TEXT NOT NULL,
  FOREIGN KEY (id) references Elements (id)
);

CREATE TABLE Annotations (
  id     TEXT PRIMARY KEY,
  stream TEXT NOT NULL,
  fbegin INT  NOT NULL,
  fend   INT  NOT NULL,
  FOREIGN KEY (id)     references Elements (id)
  -- Annotations must have a content
  -- stream must be a path identifying an own or imported stream
);

CREATE TABLE Relations (
  id TEXT PRIMARY KEY,
  FOREIGN KEY (id) references Elements (id)
  -- Relations can have a content
);

CREATE TABLE RelationMembers (
  relation   TEXT NOT NULL,
  ord        INT  NOT NULL,
  annotation TEXT NOT NULL,
  PRIMARY KEY (relation, ord),
  FOREIGN KEY (relation) REFERENCES Relations (id)
  -- for each relation, ord should be a consecutive sequence starting from 0
  -- annotation must be a path identifying an own or imported annotation
);

CREATE TABLE Bags (
  id   TEXT PRIMARY KEY,
  FOREIGN KEY (id) references Elements (id)
);

CREATE TABLE BagItems (
  bag     TEXT NOT NULL,
  ord     INT  NOT NULL,
  element TEXT NOT NULL,
  PRIMARY KEY (bag, ord)
  -- for each bag, ord must be a consecutive sequence starting from 0
  -- element must be a path identifying an own or imported element
);

CREATE TABLE Imports (
  id  TEXT PRIMARY KEY,
  url TEXT NOT NULL,
  FOREIGN KEY (id) references Elements (id)
);

CREATE TABLE Queries (
  id TEXT PRIMARY KEY,
  FOREIGN KEY (id) references Elements (id)
  -- Queries must have a content
);

CREATE TABLE Views (
  id     TEXT PRIMARY KEY,
  FOREIGN KEY (id) references Elements (id)
  -- Views must have a content
);

CREATE TABLE Resources (
  id TEXT PRIMARY KEY,
  FOREIGN KEY (id) references Elements (id)
  -- Resources must have a content (see table Contents below)
);

 
