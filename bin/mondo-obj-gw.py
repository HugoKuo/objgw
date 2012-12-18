#!/usr/bin/python -u
# Copyright (c) 2012-2013 Cloudena Taiwan Co.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# AUTHOR : Hugo Kuo

from sys import argv, exc_info, exit, stderr, stdout, path
from optparse import OptionParser, SUPPRESS_HELP
from swiftclient import Connection, ClientException, HTTPException
from ConfigParser import ConfigParser
from Queue import Empty, Queue
from os import write, environ, listdir, makedirs, utime, _exit as os_exit
import subprocess



#Append sys.path by Hugo
path.append("/opt/objgw/s3backer")
from attacher import mount, loop_map, lvm_pv_binding, lvm_vg_binding

OBJgw_path = "/opt/objgw/"
cf=ConfigParser()
cf.read('%s/objgw.conf' % OBJgw_path)

def check_vg_tables():
    conn=get_conn()
    try:
        conn.head_container("vg_tables")
    except:
        print "vg_tables does not exist , in progress to initial it"
        conn.put_container("vg_tables")

def gen_vg_info(vg_name,size,pv_numbers,pv_list):
    #vg_name="vg_cloudena_"+vg_name 
    f = open('/tmp/'+vg_name,"w")
    f.write('[INFO]\n')
    f.write('vg_name = '+vg_name+'\n')
    f.write('size = '+str(size)+'\n')
    f.write('pv_numbers = '+str(pv_numbers)+'\n')
    f.write('pv_list = '+str(pv_list))
    f.close()
    vg_info = "/tmp/"+vg_name
    return vg_info

        

def mkdirs(path):
    try:
        makedirs(path)
    except OSError, err:
        if err.errno !=EEXIST:
            raise


def get_conn():
    return Connection(cf.get('DEFAULT','AUTH_URL'),
                      cf.get('DEFAULT','ACCOUNT'),
                      cf.get('DEFAULT','KEY'))

def mount_parms():
    '''a function to generate the parameters for mounting s3backer '''
    
    parms={}
    parms["--baseURL"]=cf.get('S3BACKER','S3URL')
    parms["--accessId"]=cf.get('DEFAULT','ACCOUNT')
    parms["--accessKey"]=cf.get('DEFAULT','KEY')
    parms["--listBlocks"]=None
    parms["--blockSize"]=cf.get('S3BACKER','BLOCK_SIZE')
    parms["--size"]=cf.get('S3BACKER','SINGLE_SIZE')
    parms["--blockCacheSize"]=cf.get('S3BACKER','CACHE_BLOCKS')
    parms["--blockCacheThreads"]="30"
    parms["--debug"]=None

    return parms


def split_headers(options, prefix='', error_queue=None):
    """
    Splits 'Key: Value' strings and returns them as a dictionary.
    :param options: An array of 'Key: Value' strings
    :param prefix: String to prepend to all of the keys in the dictionary.
    :param error_queue: Queue for thread safe error reporting.
    """
    headers = {}
    for item in options:
        split_item = item.split(':', 1)
        if len(split_item) == 2:
            headers[prefix + split_item[0]] = split_item[1]
        else:
            error_string = "Metadata parameter %s must contain a ':'.\n%s" \
                            % (item, st_post_help)
            if error_queue:
                error_queue.put(error_string)
            else:
                exit(error_string)
    return headers


def gw_auth(parser=None, args=None):
    conn=get_conn()
    a=conn.head_account()
    check_vg_tables()
    return a

def gw_list_pvs(parser=None, args=None):
    conn=get_conn()
    items = conn.get_account(prefix="pv")[1]
    for item in items:
        print item.get('name')
        
    print "" 
    return "Scan existing PVs accomplish"   


def gw_list_vgs(parser=None, args=None):
    conn=get_conn()
    items = conn.get_container('vg_tables',prefix="vg")[1]
    for item in items:
        print item.get('name')
    print ""
    return "Scan all VGs accomplished"


def gw_create(parser=None,args=None):
    '''
    vg_name - vg's name prefix with VG_PREFIX flag
    pv_name - will be pv_$vg_name_$sort
    pv_count - total pvs for this vg , default to 8
    size - total capacity of this vg , default to 10T
    cache_blocks - total cache blocks , default to 1000
    mount_dir - s3backer volume mount point , default to /srv
    log_level - if enable debug , default to false
    block_size - each block object size , default to 1MB
    '''
    vg_name = '%s_%s' % (cf.get('LVM','VG_PREFIX'),args[1])
    pv_count = int(cf.get('S3BACKER','PV_COUNT'))
    single_size = int(cf.get('S3BACKER','SIZE'))/pv_count
    cache_blocks = cf.get('S3BACKER','CACHE_BLOCKS')
    mount_dir = "/srv"
    log_level = "ERROR"
    block_size = "1M"
    pv_list = []
    headers= None
    conn=get_conn()
    loop_list=[]
    #Generate pv devices list as pv_list[]
    for x in range(pv_count):
        pv_dict={}
        pv_dict['name']="pv_%s_%s" % (args[1],x)
        pv_dict['loop']=x
        pv_dict['size']=single_size    
        pv_list.append(pv_dict)
    
    #Create vg info and push into vg_tables
    vg_info=gen_vg_info(vg_name,str(single_size*pv_count),pv_count,pv_list)
    conn.put_object(container="vg_tables",obj=vg_name,
                    contents=open(vg_info,"r").read())
    
    #Create mount point on local host and swift containers , also mount to /srv/
    
    headers = split_headers(options={}, prefix='X-Container-Meta-', error_queue=None) 
    for _pv in pv_list:
        mkdirs("%s/%s" % (mount_dir, _pv['name'])) 
        conn.put_container(_pv['name'],headers=headers) 
        mount(_pv['name'],
              '/'.join([mount_dir,_pv['name']]),
              str(_pv['loop']),mount_parms()) 

        loop_dev=loop_map(_pv['name'],_pv['loop'])
        loop_list.append(loop_dev)
        lvm_pv_binding(dev=loop_dev)
    
    #Create Volume Group based
    lvm_vg_binding(vg_name,loop_list)
   
    
def gw_delete(parser=None,args=None):
    vg_name = args[1]
    conn=get_conn()
    pv_count=int(cf.get('S3BACKER','PV_COUNT'))
    pv_list=[]

    '''check if the volume group is onlinei, stop it first'''
    if subprocess.call(["vgck",cf.get('LVM','VG_PREFIX')+"_"+vg_name])== 0:
        gw_stop(vg_name=vg_name)

    #delete pv_containers , call swiftclient's client.py delete_object L#883
    for x in range(pv_count):
        pv_name="pv_"+vg_name+"_"+str(x)
        subprocess.call(["swift",
                        "-A",cf.get('DEFAULT','AUTH_URL'),
                        "-U",cf.get('DEFAULT','ACCOUNT'),
                        "-K",cf.get('DEFAULT','KEY'),
                        "delete",pv_name])
                        
    
    #conn.delete_container("pv_"+vg_name+"_"+str(x))
    conn.delete_object(container="vg_tables",obj=cf.get('LVM','VG_PREFIX')+"_"+vg_name)


def gw_stop(parser=None,vg_name=None):
    print vg_name
    if not type(vg_name)==str:
        vg_name = args[1]
        print vg_name
    else:
        vg_name=vg_name
    mount_dir = "/srv"
    mount_point = mount_dir+"/pv_"+vg_name+"*"
    mount_list = []
    #generate loop_dev list
    all_list=[i.split() for i in subprocess.check_output('pvs').splitlines()[1:]]
    loop_dev = []
    for x in range(len(all_list)):
        if all_list[x][1]==cf.get('LVM','VG_PREFIX')+"_"+vg_name:
            loop_dev.append(all_list[x][0])

    
    #unset loop base on loop_dev list
    subprocess.call([' '.join(['losetup','-d',' '.join(loop_dev)])],shell=True)
   
    for x in range(len(all_list)):
        mount_list.append(mount_dir+"/"+"pv_"+vg_name+"_"+str(x))
    print mount_list
    #umount /srv/pv_name
    subprocess.call([' '.join(['umount',' '.join(mount_list)])],shell=True)
    subprocess.call([' '.join(['rm','-r',' '.join(mount_list)])],shell=True)
    return

def parse_args(parser, args, enforce_requires=True):
    return 1, args

if __name__ == '__main__':
    parser = OptionParser(version='%prog 1.0', usage='''
Usage: %%prog <command> [options] [args]

Commands:
    auth
    create 
    delete
    start
    stop
    list_pvs
    list_vgs

Example:
    %%prog list_pvs
'''.strip('\n') % globals())

    parser.disable_interspersed_args()
    (options, args) = parse_args(parser, argv[1:], enforce_requires=False)
    parser.enable_interspersed_args()

    commands = ('auth', 'list_pvs', 'list_vgs', 'create', 'stop', 'start', 'delete')
    if not args or args[0] not in commands:
        parser.print_usage()
        if args:
            exit('no such command: %s' % args[0])
        exit()
    result = globals()['gw_%s' % args[0]](parser, argv[1:])
    print result




