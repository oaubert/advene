CREATE TABLE Version (
  version TEXT PRIMARY KEY
  -- will contain a single line with the backend version used to create this file
);

CREATE TABLE Packages (
  id TEXT PRIMARY KEY,
  uuid TEXT UNIQUE
);

CREATE TABLE Elements (
  package TEXT NOT NULL,
  id      TEXT NOT NULL,
  typ     TEXT NOT NULL,
  PRIMARY KEY (package, id)
  FOREIGN KEY (package) references Packages (id)
  -- type must be m,a,r,t,l,q,v,R,i
);

CREATE TABLE Meta (
  package TEXT NOT NULL,
  element TEXT NOT NULL,
  key     TEXT NOT NULL,
  value   TEXT NOT NULL,
  PRIMARY KEY (package, element, key),
  FOREIGN KEY (package) references Packages (id)
  -- if column element is not an empty string,
  -- then it must reference Elements (package, id)
  -- else, the metadata is about the package itself
);

CREATE TABLE Contents (
  package  TEXT NOT NULL,
  element  TEXT NOT NULL,
  mimetype TEXT NOT NULL,
  schema   TEXT,
  data     BLOB,
  url      TEXT,
  PRIMARY KEY (package, element),
  FOREIGN KEY (package, element) references Elements  (package, id)
  -- only elements with a content should be referenced by element
  -- if not null, schema must be a path identifying an own or imported resource
  -- exactly one of content and url must be not null
);

CREATE TABLE Medias (
  package TEXT NOT NULL,
  id      TEXT NOT NULL,
  url     TEXT NOT NULL,
  PRIMARY KEY (package, id),
  FOREIGN KEY (package, id) references Elements (package, id)
  -- typ of the referenced element must me 'm'
);

CREATE TABLE Annotations (
  package TEXT NOT NULL,
  id      TEXT NOT NULL,
  media   TEXT NOT NULL,
  fbegin  INT  NOT NULL,
  fend    INT  NOT NULL,
  PRIMARY KEY (package, id),
  FOREIGN KEY (package, id) references Elements (package, id)
  -- typ of the referenced element must me 'a'
  -- Annotations must have a content
  -- media must be the uuid-ref of an own or imported media
);

CREATE TABLE RelationMembers (
  package    TEXT NOT NULL,
  relation   TEXT NOT NULL,
  ord        INT  NOT NULL,
  annotation TEXT NOT NULL,
  PRIMARY KEY (package, relation, ord),
  FOREIGN KEY (package, relation) REFERENCES Relations (package, id)
  -- typ of the referenced element must me 'r'
  -- for each relation, ord should be a consecutive sequence starting from 0
  -- annotation must be the uuid-ref of an own or imported annotation
);

CREATE TABLE ListItems (
  package TEXT NOT NULL,
  list    TEXT NOT NULL,
  ord     INT  NOT NULL,
  element TEXT NOT NULL,
  PRIMARY KEY (package, list, ord),
  FOREIGN KEY (package, list) references Elements (package, id)
  -- typ of the referenced element must me 'l'
  -- for each list, ord must be a consecutive sequence starting from 0
  -- element must be the uuid-ref of an own or imported element
);

CREATE TABLE Imports (
  package TEXT NOT NULL,
  id      TEXT NOT NULL,
  url     TEXT NOT NULL,
  uuid    TEXT,
  PRIMARY KEY (package, id),
  FOREIGN KEY (package, id) references Elements (package, id)
  -- typ of the referenced element must me 'i'
  -- if not null, uuid should be the uuid of the imported package
);

CREATE TABLE Tagged (
  package TEXT NOT NULL,
  element TEXT NOT NULL,
  tag     TEXT NOT NULL,
  PRIMARY KEY (package, element, tag)
  -- element must be the uuid-ref of an own or imported element
  -- tag must be the uuid-ref of an own or imported tag
);
