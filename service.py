# -*- coding: utf-8 -*-
# Subdivx.com subtitles, based on a mod of Undertext subtitles
# Adaptation: enric_godes@hotmail.com | Please use email address for your
# comments
# Port to XBMC 13 Gotham subtitles infrastructure: cramm, Mar 2014

from __future__ import print_function
from json import loads
import os
from os.path import join as pjoin
import os.path
from pprint import pformat
import re
import shutil
import sys
import time
import HTMLParser
from unicodedata import normalize
from urllib import FancyURLopener, unquote, unquote_plus, quote_plus, urlencode
from urlparse import parse_qs

try:
    import xbmc
except ImportError:
    if len(sys.argv) > 1 and sys.argv[1] == 'test':
        import unittest  # NOQA
        try:
            import mock  # NOQA
        except ImportError:
            print("You need to install the mock Python library to run "
                  "unit tests.\n")
            sys.exit(1)
else:
    from xbmc import (LOGDEBUG, LOGINFO, LOGNOTICE, LOGWARNING, LOGERROR,
                      LOGSEVERE, LOGFATAL, LOGNONE)
    import xbmcaddon
    import xbmcgui
    import xbmcplugin
    import xbmcvfs

__addon__ = xbmcaddon.Addon()
__author__     = __addon__.getAddonInfo('author')
__scriptid__   = __addon__.getAddonInfo('id')
__scriptname__ = __addon__.getAddonInfo('name')
__version__    = __addon__.getAddonInfo('version')
__language__   = __addon__.getLocalizedString

__cwd__        = xbmc.translatePath(__addon__.getAddonInfo('path').decode("utf-8"))
__profile__    = xbmc.translatePath(__addon__.getAddonInfo('profile').decode("utf-8"))


MAIN_SUBWIKI_URL = "http://www.subswiki.com/"
SEARCH_PAGE_URL = MAIN_SUBWIKI_URL + \
    "search.php?search=%(query)s"

INTERNAL_LINK_URL_BASE = "plugin://%s/?"
SUB_EXTS = ['srt', 'sub', 'txt']
HTTP_USER_AGENT = "User-Agent=Mozilla/5.0 (Windows; U; Windows NT 6.1; en-US; rv:1.9.2.3) Gecko/20100401 Firefox/3.6.3 ( .NET CLR 3.5.30729)"

PAGE_ENCODING = 'utf-8'


# ============================
# Regular expression patterns
# ============================

SUBTITLE_INITIAL_SEARCH = re.compile(r'''<a\s+href="/(?P<url_id>film.+?|serie.+?)"\s*>(?P<text>.+?)</a>''',
                         re.IGNORECASE | re.DOTALL | re.VERBOSE | re.UNICODE |
                         re.MULTILINE)

SUBTITLE_SECOND_SEARCH=re.compile(r'''<table\s+width="90%"\s+border="0"\s+align="center">[\s\r\n]*<tr>[\s\r\n]*<td\s+colspan="2"\s+class="NewsTitle"\s+style="font-size:13px;"\s+height="25">[\s\r\n]*<img\s+src="/images/folder_page.png"\s+width="16"\s+height="16"\s*/>(?P<version>[\s\S]*?)</td>(?P<content>.*?)</table>''', re.IGNORECASE |
                              re.DOTALL | re.MULTILINE | re.UNICODE)


SUBTITULE_FINAL_SEARCH=re.compile(r'''<td\s+width="21%"\s+class="language">(?P<language>[\s\S]*?)</td>[\s\r\n]*<td\s+width="19%">[\s\r\n]*<strong>[\w\s.]*<\/strong>[\s\r\n]*<\/td>[\s\r\n]*<td\s+colspan="3">[\s\r\n]*<img\s+src="/images/download.png"\s+width="16"\s+height="16"\s*/>(?P<content>.*?)</td>''', re.IGNORECASE |
                              re.DOTALL | re.MULTILINE | re.UNICODE)

SUBTITULE_LAST_SEARCH=re.compile(r'''<a href="(?P<download>.*?)"(.*?)>(?P<download_descr>.*?)</a>''', re.IGNORECASE |
                              re.DOTALL | re.MULTILINE | re.UNICODE)

# ==========
# Functions
# ==========


def is_subs_file(fn):
    """Detect if the file has an extension we recognise as subtitle."""
    ext = fn.split('.')[-1]
    return ext.upper() in [e.upper() for e in SUB_EXTS]


def log(msg, level=LOGDEBUG):
    fname = sys._getframe(1).f_code.co_name
    s = u"SUBSWIKI - %s: %s" % (fname, msg)
    xbmc.log(s.encode('utf-8'), level=level)


def get_url(url):
    class MyOpener(FancyURLopener):
        #version = HTTP_USER_AGENT
        version = ''
    my_urlopener = MyOpener()
    log(u"Fetching %s" % url)
    try:
        response = my_urlopener.open(url)        
        content = response.read()                
    except Exception:
        log(u"Failed to fetch %s" % url, level=LOGWARNING)
        ucontent = None    
    ucontent = unicode(content, 'utf-8')
    h = HTMLParser.HTMLParser()
    ucontent = h.unescape(ucontent)    
    return ucontent


def _downloads2rating(downloads):
    rating = downloads / 1000
    if rating > 10:
        rating = 10
    return rating


def get_all_subs(searchstring, languages, file_orig_path, istvshow):
    subs_list = []
    bool = True    
    while bool:
        bool = False
        log(u"Trying string= %s" % searchstring)
        url = SEARCH_PAGE_URL % {'query': quote_plus(searchstring)}
        content = get_url(url)
        if content is None or not SUBTITLE_INITIAL_SEARCH.search(content):            
            break
        for match in SUBTITLE_INITIAL_SEARCH.finditer(content):
            groups = match.groupdict()
            url_id = groups['url_id']
            log(u'%s'%(url_id))
            if istvshow and 'film' in url_id:
                log(u'Entro')
                continue
            if not istvshow and 'serie' in url_id:
                log(u'Entro1')
                continue
            descr = groups['text']            
            descr = descr.strip()
            # Remove new lines
            descr = re.sub('\n', '', descr)                            
            # Remove HTML tags
            descr = re.sub(r'<[^<]+?>', '', descr)
            url_search= MAIN_SUBWIKI_URL + url_id            
            content2=get_url(url_search)
            content2 = re.sub('\n', '', content2)
            content2 = re.sub('\r', '', content2)
            try:
                log(u'Subtitles found: [url_id = %s] "%s"' % (url_id,
                                                                    descr))
            except Exception:
                pass            
            if content2 is None or not SUBTITLE_SECOND_SEARCH.search(content2):                
                break
            for match2 in SUBTITLE_SECOND_SEARCH.finditer(content2):
                groups2 = match2.groupdict()               
                descr2 = descr+" "+groups2['version']               
                
                descr2 = descr2.strip()
                # Remove new lines
                descr2 = re.sub('\n', ' ', descr2)                            
                # Remove HTML tags
                descr2 = re.sub(r'<[^<]+?>', '', descr2)                
                content3 = groups2['content']
                                               
                if content3 is None or not SUBTITULE_FINAL_SEARCH.search(content3):                    
                    break
                                                
                for match3 in SUBTITULE_FINAL_SEARCH.finditer(content3):
                    groups3 = match3.groupdict()
                    
                    language= groups3['language']
                                                                            
                    if  languages in language:
                        content4=groups3['content']                        
                        if content4 is None or not SUBTITULE_LAST_SEARCH.search(content4):                    
                            break
                        for match4 in SUBTITULE_LAST_SEARCH.finditer(content4):
                            groups4 = match4.groupdict()
                            
                            download_id= groups4['download']
                            download_descr= groups4['download_descr']
                            
                            descr3=descr2+" "+download_descr
                            # If our actual video file's name appears in the description
                            # then set sync to True because it has better chances of its
                            # synchronization to match
                            _, fn = os.path.split(file_orig_path)
                            name, _ = os.path.splitext(fn)
                            sync = re.search(re.escape(name), descr3, re.I) is not None
        
                            try:
                                log(u'Subtitles found: (download_id = %s) "%s"' % (download_id,
                                                                                   language))
                            except Exception:
                                pass
                            item = {
                                    'descr': descr3,
                                    'sync': sync,
                                    'download_id': download_id.decode(PAGE_ENCODING),
                                    'language':language,                        
                                    'downloads': 0,
                                    'rating': 0,
                                    'score': 0,
                            }
                            subs_list.append(item)
                    else:
                        log(u'Subtitles found no match to languages: "%s - %s"' % (language, languages))
                        
    # Put subs with sync=True at the top
    subs_list = sorted(subs_list, key=lambda s: s['sync'], reverse=True)
    log(u"Returning %s" % pformat(subs_list))
    return subs_list


def append_subtitle(item, filename):
    item_label = item['language']
    listitem = xbmcgui.ListItem(
        label=item_label,
        label2=item['descr'],
        iconImage=str(item['rating']),
        thumbnailImage=''
    )
    listitem.setProperty("sync", 'true' if item["sync"] else 'false')
    listitem.setProperty("hearing_imp",
                         'true' if item.get("hearing_imp", False) else 'false')

    # Below arguments are optional, they can be used to pass any info needed in
    # download function. Anything after "action=download&" will be sent to
    # addon once user clicks listed subtitle to download
    url = INTERNAL_LINK_URL_BASE % __scriptid__
    xbmc_url = build_xbmc_item_url(url, item, filename)
    # Add it to list, this can be done as many times as needed for all
    # subtitles found
    xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]),
                                url=xbmc_url,
                                listitem=listitem,
                                isFolder=False)


def build_xbmc_item_url(url, item, filename):
    """Return an internal Kodi pseudo-url for the provided sub search result"""
    try:
        xbmc_url = url + urlencode((('id', item['download_id']),
                                    ('filename', filename)))
    except UnicodeEncodeError:
        # Well, go back to trying it with its original latin1 encoding
        try:
            download_id = item['download_id'].encode(PAGE_ENCODING)
            xbmc_url = url + urlencode((('id', download_id),
                                        ('filename', filename)))
        except Exception:
            log('Problematic download_id: %s' % download_id)
            raise
    return xbmc_url


def Search(item):
    """Called when subtitle download is requested from XBMC."""
    log(u'item = %s' % pformat(item))
    # Do what's needed to get the list of subtitles from service site
    # use item["some_property"] that was set earlier.
    # Once done, set xbmcgui.ListItem() below and pass it to
    # xbmcplugin.addDirectoryItem()
    file_original_path = item['file_original_path']
    title = item['title']
    tvshow = item['tvshow']
    season = item['season']
    episode = item['episode']
    istvshow = False
    if item['manual_search']:
        searchstring = unquote(item['manual_search_string'])
    elif tvshow:
        istvshow = True
        searchstring = "%s - %#02dx%#02d" % (tvshow, int(season), int(episode))
    else:
        searchstring = title
    log(u"Search string = %s" % searchstring)    
    subs_list = get_all_subs(searchstring, u'Español', file_original_path, istvshow)

    for sub in subs_list:
        append_subtitle(sub, file_original_path)


def _wait_for_extract(workdir, base_filecount, base_mtime, limit):
    waittime = 0
    filecount = base_filecount
    newest_mtime = base_mtime
    while (filecount == base_filecount and waittime < limit and
           newest_mtime == base_mtime):
        # wait 1 second to let the builtin function 'XBMC.Extract' unpack
        time.sleep(1)
        files = os.listdir(workdir)
        filecount = len(files)
        # Determine if there is a newer file created (marks that the extraction
        # has completed)
        for fname in files:
            if not is_subs_file(fname):
                continue
            fname = fname
            mtime = os.stat(pjoin(workdir, fname)).st_mtime
            if mtime > newest_mtime:
                newest_mtime = mtime
        waittime += 1
    return waittime != limit


def _handle_compressed_subs(workdir, compressed_file):
    MAX_UNZIP_WAIT = 15
    files = os.listdir(workdir)
    filecount = len(files)
    max_mtime = 0
    # Determine the newest file
    for fname in files:
        if not is_subs_file(fname):
            continue
        mtime = os.stat(pjoin(workdir, fname)).st_mtime
        if mtime > max_mtime:
            max_mtime = mtime
    base_mtime = max_mtime
    # Wait 2 seconds so that the unpacked files are at least 1 second newer
    time.sleep(2)
    xbmc.executebuiltin("XBMC.Extract(%s, %s)" % (
                        compressed_file.encode("utf-8"),
                        workdir.encode("utf-8")))

    retval = False
    if _wait_for_extract(workdir, filecount, base_mtime, MAX_UNZIP_WAIT):
        files = os.listdir(workdir)
        for fname in files:
            # There could be more subtitle files, so make
            # sure we get the newly created subtitle file
            if not is_subs_file(fname):
                continue
            fpath = pjoin(workdir, fname)
            if os.stat(fpath).st_mtime > base_mtime:
                # unpacked file is a newly created subtitle file
                retval = True
                break

    if retval:
        log(u"Unpacked subtitles file '%s'" % normalize_string(fpath))
    else:
        log(u"Failed to unpack subtitles", level=LOGSEVERE)
    return retval, fpath


def _save_subtitles(workdir, content):
    header = content[:4]
    if header == 'Rar!':
        type = '.rar'
        is_compressed = True
    elif header == 'PK\x03\x04':
        type = '.zip'
        is_compressed = True
    else:
        # Never found/downloaded an unpacked subtitles file, but just to be
        # sure ...
        # Assume unpacked sub file is a '.srt'
        type = '.srt'
        is_compressed = False
    tmp_fname = pjoin(workdir, "subswiki" + type)
    log(u"Saving subtitles to '%s'" % normalize_string(tmp_fname))
    try:
        with open(tmp_fname, "wb") as fh:
            fh.write(content)
    except Exception:
        log(u"Failed to save subtitles to '%s'" % normalize_string(tmp_fname), level=LOGSEVERE)
        return None
    else:
        if is_compressed:
            rval, fname = _handle_compressed_subs(workdir, tmp_fname)
            if rval:
                return fname
        else:
            return tmp_fname
    return None

def rmgeneric(path, __func__):
    try:
        __func__(path)
        log(u"Removed %s" % normalize_string(path))
    except OSError, (errno, strerror):
        log(u"Error removing %(path)s, %(error)s" % {'path' : normalize_string(path), 'error': strerror }, level=LOGFATAL)

def removeAll(dir):
    if not os.path.isdir(dir):
        return
    files = os.listdir(dir)
    for file in files:
        if os.path.isdir(pjoin(dir, file)):
            removeAll(file)
        else:
            f=os.remove
            rmgeneric(pjoin(dir, file), f)
    f=os.rmdir
    rmgeneric(dir, f)

def ensure_workdir(workdir):
    # Cleanup temp dir, we recommend you download/unzip your subs in temp
    # folder and pass that to XBMC to copy and activate
    if xbmcvfs.exists(workdir):
        removeAll(workdir)
    xbmcvfs.mkdirs(workdir)
    return xbmcvfs.exists(workdir)


def Download(download_id, workdir):
    """Called when subtitle download is requested from XBMC."""
    subtitles_list = []
    # Get the page with the subtitle link,
    # i.e. http://www.subdivx.com/X6XMjE2NDM1X-iron-man-2-2010
    subtitle_detail_url = MAIN_SUBWIKI_URL + download_id
    download_content = get_url(subtitle_detail_url)
    if download_content is None:
        log(u"Expected content not found in selected subtitle detail page",
                level=LOGFATAL)
        return subtitles_list
    else:
        saved_fname = _save_subtitles(workdir, download_content)
        if saved_fname:
            subtitles_list.append(saved_fname)
        else:
            log(u"Expected content not found in selected subtitle detail page",
            level=LOGFATAL)
    return subtitles_list


def _double_dot_fix_hack(video_filename):

    log(u"video_filename = %s" % video_filename)

    work_path = video_filename
    if _subtitles_setting('storagemode'):
        custom_subs_path = _subtitles_setting('custompath')
        if custom_subs_path:
            _, fname = os.path.split(video_filename)
            work_path = pjoin(custom_subs_path, fname)

    log(u"work_path = %s" % work_path)
    parts = work_path.rsplit('.', 1)
    if len(parts) > 1:
        rest = parts[0]
        bad = rest + '..' + 'srt'
        old = rest + '.es.' + 'srt'
        if xbmcvfs.exists(bad):
            log(u"%s exists" % bad)
            if xbmcvfs.exists(old):
                log(u"%s exists, renaming" % old)
                xbmcvfs.delete(old)
            log(u"renaming %s to %s" % (bad, old))
            xbmcvfs.rename(bad, old)

def normalize_string(str):
    return normalize('NFKD', unicode(unicode(str, 'utf-8'))).encode('ascii',
                                                                    'ignore')

def get_params(argv):
    params = {}
    qs = argv[2].lstrip('?')
    if qs:
        if qs.endswith('/'):
            qs = qs[:-1]
        parsed = parse_qs(qs)
        for k, v in parsed.iteritems():
            params[k] = v[0]
    return params


def main():
    """Main entry point of the script when it is invoked by XBMC."""
    log(u"Version: %s" % __version__, level=LOGINFO)

    # Get parameters from XBMC and launch actions
    params = get_params(sys.argv)

    if params['action'] in ('search', 'manualsearch'):
        item = {
            'temp': False,
            'rar': False,
            'year': xbmc.getInfoLabel("VideoPlayer.Year"),
            'season': str(xbmc.getInfoLabel("VideoPlayer.Season")),
            'episode': str(xbmc.getInfoLabel("VideoPlayer.Episode")),
            'tvshow': normalize_string(xbmc.getInfoLabel("VideoPlayer.TVshowtitle")),
            # Try to get original title
            'title': normalize_string(xbmc.getInfoLabel("VideoPlayer.OriginalTitle")),
            # Full path of a playing file
            'file_original_path': unquote(xbmc.Player().getPlayingFile().decode('utf-8')),
            '3let_language': [],
            '2let_language': [],
            'manual_search': 'searchstring' in params,
        }

        if 'searchstring' in params:
            item['manual_search_string'] = params['searchstring']

        for lang in unquote(params['languages']).decode('utf-8').split(","):
            item['3let_language'].append(xbmc.convertLanguage(lang, xbmc.ISO_639_2))
            item['2let_language'].append(xbmc.convertLanguage(lang, xbmc.ISO_639_1))

        if not item['title']:
            # No original title, get just Title
            item['title'] = normalize_string(xbmc.getInfoLabel("VideoPlayer.Title"))

        if "s" in item['episode'].lower():
            # Check if season is "Special"
            item['season'] = "0"
            item['episode'] = item['episode'][-1:]

        if "http" in item['file_original_path']:
            item['temp'] = True

        elif "rar://" in item['file_original_path']:
            item['rar'] = True
            item['file_original_path'] = os.path.dirname(item['file_original_path'][6:])

        elif "stack://" in item['file_original_path']:
            stackPath = item['file_original_path'].split(" , ")
            item['file_original_path'] = stackPath[0][8:]

        Search(item)

    elif params['action'] == 'download':
        workdir = pjoin(__profile__, 'temp')
        # Make sure it ends with a path separator (Kodi 14)
        workdir = workdir + os.path.sep
        workdir = xbmc.translatePath(workdir)

        ensure_workdir(workdir)

        # We pickup our arguments sent from the Search() function
        subs = Download(params["id"], workdir)
        # We can return more than one subtitle for multi CD versions, for now
        # we are still working out how to handle that in XBMC core
        for sub in subs:
            listitem = xbmcgui.ListItem(label=sub)
            xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]), url=sub,
                                        listitem=listitem, isFolder=False)

    # Send end of directory to XBMC
    xbmcplugin.endOfDirectory(int(sys.argv[1]))

    
if __name__ == '__main__':
      main()
    
# if __name__ == '__main__':    
#      item = {
#              'temp': False,
#              'rar': False,
#              'year': '2015',
#              'season': None,
#              'episode': None,
#              'tvshow': None,
#               # Try to get original title
#              'title': 'Avenger',
#               # Full path of a playing file
#              'file_original_path': unquote(xbmc.Player().getPlayingFile().decode('utf-8')),
#              '3let_language': [],
#              '2let_language': [],
#              'manual_search': '',
#          }   
#      Search(item)