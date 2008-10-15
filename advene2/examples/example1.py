from advene.model.core.package import Package
from advene.model.core.media import FOREF_PREFIX

frame_of_reference = FOREF_PREFIX + "ms;o=0"

# This demonstrate how to create and save a package

# create a package with a relative URL
# NB: this is a *URL*, not a filename (that could be http://...)
# so use "/" as a separator, even in MS Windows
p = Package("examples/example1.bxp", create=True)

# add a resource to that package,
# the content is given by a URL, relative to the package's URL
r = p.create_resource("r", "text/x-python", url="example1.py")

# we save the current state of our package to another file
# NB: this is a filename, the separator is OS dependant
p.save_as("examples/example1-sav.bxp", erase=True)

# we now add a media
m = p.create_media("m", "dvd://", frame_of_reference)
p.save()

# we now save under a new name, and work on the new file
p.save_as("examples/example1-new.bxp", erase=True, change_url=True)
a = p.create_annotation("a", m, 0, 60, "text/plain")
p.save()

# Don't forget to close your package once you are done
p.close()


# We now load an existing package
# NB: this is still a URL, even if it can be relative
q = Package("examples/example1-new.bxp")

# list all elements in q
for e in q.own:
    print e.id,
print

q.close()


# as simple as that
