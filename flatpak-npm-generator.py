#!/usr/bin/env python3

import sys
import json
import base64
import binascii
import urllib.request
import urllib.parse

electron_arches = {
    "ia32": "i386",
    "x64": "x86_64",
    "arm": "arm"
}

include_devel = True

args = sys.argv[1:]
while len(args) and args[0].startswith("-"):
    if args[0] == '--production':
        include_devel = False
    args = args[1:] # shift

if len(args) != 2:
    print("Usage: flatpak-npm-generator [--production] package-lock.json generated-sources.json")
    sys.exit(1)

lockfile = sys.argv[1]
outfile =  sys.argv[2]

f = open(lockfile, 'r')

root = json.loads(f.read ())

def getModuleSources(module, seen={}):
    sources = []

    version = module["version"]
    added_url = None

    if module.get("dev", False) and not include_devel:
        pass
    if module.get("bundled", False):
        pass
    elif module.get("resolved", False) or (version.startswith("http") and not version.endswith(".git")):
        if module.get("resolved", False):
            url = module["resolved"]
        else:
            url = module["version"]
        added_url = url
        integrity = module["integrity"]
        if not integrity in seen:
            seen[integrity] = True
            (integrity_type, integrity_base64) = integrity.split("-", 2);
            hex = binascii.hexlify(base64.b64decode(integrity_base64)).decode('utf8')
            source = { "type": "file",
                       "url": url,
                       "dest": "npm-cache/_cacache/content-v2/%s/%s/%s" % (integrity_type, hex[0:2], hex[2:4]),
                       "dest-filename": hex[4:]
            }
            source[integrity_type] = hex;
            sources.append(source)

    if added_url:
        # Special case electron, adding sources for the electron binaries
        tarname = added_url[added_url.rfind("/")+1:]
        if tarname.startswith("electron-") and tarname[len("electron-")].isdigit() and tarname.endswith(".tgz"):
            electron_version = tarname[len("electron-"):-len(".tgz")]

            shasums_url = "https://github.com/electron/electron/releases/download/v" + electron_version + "/SHASUMS256.txt"
            f = urllib.request.urlopen(shasums_url)
            shasums={}
            shasums_data = f.read().decode("utf8")
            for line in shasums_data.split('\n'):
                l = line.split();
                if len(l) == 2:
                    shasums[l[1][1:]] = l[0]

            mini_shasums = ""
            for arch in electron_arches.keys():
                basename = "electron-v" + electron_version + "-linux-" + arch + ".zip"
                source = { "type": "file",
                           "only-arches": [electron_arches[arch]],
                           "url": "https://github.com/electron/electron/releases/download/v" + electron_version + "/" + basename,
                           "sha256": shasums[basename],
                           "dest": "npm-cache"
                }
                sources.append(source)
                mini_shasums = mini_shasums + shasums[basename] + " *" + basename + "\n"
            source = { "type": "file",
                       "url": "data:" + urllib.parse.quote(mini_shasums.encode("utf8")),
                       "dest": "npm-cache",
                       "dest-filename": "SHASUMS256.txt-" + electron_version
            }
            sources.append(source)

    if "dependencies" in module:
        deps = module["dependencies"]
        for dep in deps:
            child_sources = getModuleSources(deps[dep], seen)
            sources = sources + child_sources

    return sources

sources = getModuleSources(root)

fo = open(outfile, 'w')
fo.write (json.dumps(sources, indent=4))
