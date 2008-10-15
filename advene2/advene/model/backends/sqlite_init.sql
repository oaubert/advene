-- about NULL values and foreign keys
-- ==================================
--
-- we never use NULL values because they have a special behaviour with respect
-- to comparisons (they are not even equal to themselves)
--
-- the only case where this special behaviour may be useful to us is w.r.t.
-- foreign keys, which are not bound to hold for NULL values.
-- however, since foreign keys are not checked by Sqlite, we use empty strings
-- instead of NULL values, and declare foreign keys even if they are to be
-- violated by empty strings

CREATE TABLE Version (
  version TEXT PRIMARY KEY
  -- will contain a single line with the backend version used to create this file
);

CREATE TABLE Packages (
  id  TEXT PRIMARY KEY,
  uri TEXT NOT NULL,
  url TEXT NOT NULL 
  -- column url is set when binding a pattern, to remember with which URL the
  --  package was open
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
  value   TEXT NOT NULL, -- text value
  value_p TEXT NOT NULL, -- element value (prefix)
  value_i TEXT NOT NULL, -- element value (identifier)
  PRIMARY KEY (package, element, key),
  FOREIGN KEY (package) references Packages (id)
  -- if column element is not an empty string,
  -- then it must reference Elements (package, id)
  -- else, the metadata is about the package itself
  --
  -- either value or value_i must be empty
);

CREATE TABLE Contents (
  package  TEXT NOT NULL,
  element  TEXT NOT NULL,
  mimetype TEXT NOT NULL,
  schema_p TEXT NOT NULL,
  schema_i TEXT NOT NULL,
  url      TEXT NOT NULL,
  data     BLOB NOT NULL,
  PRIMARY KEY (package, element),
  FOREIGN KEY (package, element)  references Elements (package, id),
  -- the following foreign key may be violated by empty strings in schema_p
  FOREIGN KEY (package, schema_p) references Imports  (package, id)
  -- only elements with a content should be referenced by element
  -- if not empty, schema_i must identify an own or directly imported (from 
  -- schema_p) resource
);

CREATE TABLE Medias (
  package TEXT NOT NULL,
  id      TEXT NOT NULL,
  url     TEXT NOT NULL,
  foref   TEXT NOT NULL, -- Frame Of REFerence
  PRIMARY KEY (package, id),
  FOREIGN KEY (package, id) references Elements (package, id)
  -- typ of the referenced element must me 'm'
);

CREATE TABLE Annotations (
  package TEXT NOT NULL,
  id      TEXT NOT NULL,
  media_p TEXT NOT NULL,
  media_i TEXT NOT NULL,
  fbegin  INT  NOT NULL,
  fend    INT  NOT NULL,
  PRIMARY KEY (package, id),
  FOREIGN KEY (package, id)      references Elements (package, id),
  -- the following foreign key may be violated by empty strings in media_p
  FOREIGN KEY (package, media_p) references Imports  (package, id)
  -- typ of the referenced element must me 'a'
  -- Annotations must have a content
  -- media_i must be the id of an own or directly imported (from media_p) media
);

CREATE TABLE RelationMembers (
  package  TEXT NOT NULL,
  relation TEXT NOT NULL,
  ord      INT  NOT NULL,
  member_p TEXT NOT NULL,
  member_i TEXT NOT NULL,
  PRIMARY KEY (package, relation, ord),
  FOREIGN KEY (package, relation) REFERENCES Relations (package, id),
  -- the following foreign key may be violated by empty strings in member_p
  FOREIGN KEY (package, member_p) REFERENCES Imports   (package, id)
  -- typ of the referenced element must me 'r'
  -- for each relation, ord should be a consecutive sequence starting from 0
  -- member_i must be the id of an own or directly imported (from member_p)
  -- annotation
);

CREATE TABLE ListItems (
  package TEXT NOT NULL,
  list    TEXT NOT NULL,
  ord     INT  NOT NULL,
  item_p  TEXT NOT NULL,
  item_i  TEXT NOT NULL,
  PRIMARY KEY (package, list, ord),
  FOREIGN KEY (package, list)   references Elements (package, id),
  -- the following foreign key may be violated by empty strings in item_p
  FOREIGN KEY (package, item_p) references Imports  (package, id)
  -- typ of the referenced element must me 'l'
  -- for each list, ord must be a consecutive sequence starting from 0
  -- item_i must be the id of an own or directly imported (from item_p)
  -- element
);

CREATE TABLE Imports (
  package TEXT NOT NULL,
  id      TEXT NOT NULL,
  url     TEXT NOT NULL,
  uri     TEXT NOT NULL,
  PRIMARY KEY (package, id),
  FOREIGN KEY (package, id) references Elements (package, id)
  -- typ of the referenced element must me 'i'
  -- if not empty, uri should be the uri of the directly imported package
);

CREATE TABLE Tagged (
  package   TEXT NOT NULL,
  element_p TEXT NOT NULL,
  element_i TEXT NOT NULL,
  tag_p     TEXT NOT NULL,
  tag_i     TEXT NOT NULL,
  PRIMARY KEY (package, element_p, element_i, tag_p, tag_i),
  -- the following foreign key may be violated by empty strings in *_p
  FOREIGN KEY (package, element_p) references Imports  (package, id),
  FOREIGN KEY (package, tag_p)     references Imports  (package, id)
  -- element_i must be the id of an own or directly imported (from 
  -- element_p) element
  -- tag_i must be the id of an own or directly imported (from tag_p) tag
);
