import dnf
import dnf.callback
import fnmatch
import hawkey
import json

class DNFCacheMDProgress(dnf.callback.DownloadProgress):
  """Metadata Download callback handler."""
  def __init__(self, cb=None):
    super(DNFCacheMDProgress, self).__init__()
    self._last = -1.0
    self._cb = cb

  def start(self, total_files, total_size):
    self._last = -1.0

  def end(self, payload, status, msg):
    name = str(payload)
    if status == dnf.callback.STATUS_OK:
      if self._cb is not None:
        self._cb(name, 1.0)

  def progress(self, payload, done):
    name = str(payload)
    cur_total_bytes = payload.download_size
    if cur_total_bytes:
      frac = done / float(cur_total_bytes)
    else:
      frac = 0.0

    if frac > self._last + 0.01:
      self._last = frac

    if self._cb is not None:
      self._cb(name, frac)


class DNFCache(object):
  def __init__(self, db=dnf.Base(), md_progress_cb=None):
    if not isinstance(db, dnf.Base):
      raise Exception('Expected dnf.Base object.')

    self._db = db
    self._md_progress = DNFCacheMDProgress(cb=md_progress_cb)

    RELEASE_VER = dnf.rpm.detect_releasever( db.conf.installroot )
    self._db.conf.substitutions['releasever'] = RELEASE_VER

    # we're a cache after all
    cli_cache = dnf.conf.CliCache(self._db.conf)
    self._db.conf.cachedir = cli_cache.cachedir
    self._system_cachedir = cli_cache.system_cachedir

    self._db.read_all_repos()

    # attach repo metadata progress
    self._db.repos.all().set_progress_bar(self._md_progress)

    # fill the sack with goodies
    self._db.fill_sack()

    q = self._db.sack.query()
    self._candidate = list( q.available() )
    self._installed = list( q.installed() )

    self._c = {}

    for p in self._candidate:
      self._c[p.name] = DNFCachePackage(name=p.name, candidate=p)

    for p in self._installed:
      if not p.name in self._c:
        self._c[p.name] = DNFCachePackage(name=p.name)

      self._c[p.name].installed = p


  def total_candidates(self):
    return len(self._candidates)

  def total_installed(self):
    return len(self._installed)

  def package_list(self):
    return list(self._c.values())

  def package(self, name):
    if not name in self._c:
      return None

    return self._c[name]

  def is_installed(self, name):
    if not name in self._c:
      return False

    return self._c[name].installed is not None

  def search_installed(self, name):
    found = []

    for p in self._installed:
      if fnmatch.fnmatch(p.name, name):
        found.append( self._c[p.name] )

    return found

  def __len__(self):
    return len(self._c)

  def __contains__(self, key):
    return key in self._c

  def __getitem__(self, key):
    if not key in self._c:
      raise KeyError('Package %s not found in cache.' % key)

    return self._c[key]

  def __iter__(self):
    return iter(self._c)

  def items():
    return self._c.items()

  def itervalues(self):
    return iter(self._c)

  def get(self, key):
    if not key in self._c:
      return None

    return self._c[key]

  def keys(self):
    return self._c.keys()

  def itervalues(self):
    return self._c.itervalues()

  def values(self):
    return self._c.values()


class DNFCachePackage(object):
  def __init__(self, name='', candidate=None, installed=None):
    self._name = name
    self._candidate = candidate
    self._installed = installed
    self._records = {}

  def __str__(self):
    return self._name

  @property
  def name(self):
    return self._name

  @property
  def summary(self):
    return self.candidate.summary

  @property
  def version(self):
    return self.candidate.version

  @property
  def shortname(self):
    return self._name

  @property
  def pkname(self):
    repo = 'installed'
    if self._installed is None:
      repo = self.candidate.repoid

    return '%s;%s-%s;%s;%s' % (self._name, self.candidate.version, self.candidate.release, self.candidate.arch, repo)

  @property
  def cname(self):
    repo = 'installed'
    if self._installed is None:
      repo = self.candidate.repoid

    return '%s,%s,%s,%s,%s,%s' % (self._name, self.candidate.epoch, self.candidate.version, self.candidate.release, self.candidate.arch, repo)

  @name.setter
  def name(self, name):
    self._name = name

  @property
  def candidate(self):
    return self._candidate

  @candidate.setter
  def candidate(self, candidate):
    self._candidate = candidate

  @property
  def installed(self):
    return self._installed

  @installed.setter
  def installed(self, installed):
    self._installed = installed

  def record(self, name):
    if not name in self._records:
      raise KeyError('%s not a valid record' % (name))

    return self._records[name]

  def has_record(self, name):
    return name in self._records

  def record_set(self, name, value):
    self._records[name] = value

  def is_installed(self):
    return self._installed is not None

