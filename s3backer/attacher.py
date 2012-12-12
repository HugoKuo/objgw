import os 
import subprocess
import httplib2


def mount(container , path , core , parms):
    '''
    container - the swift container which is for s3backer
    path - localhost directory for mounting specified container
    parms - a list includes other options for mounting
    '''
    pp_dict=parms
    pp_list=[]
    for k,v in pp_dict.iteritems():
        if v:
            pp_list.append('='.join([k,v]))
        else:
            pp_list.append(k)
    
    subprocess.call(' '.join(["taskset","-c",core,"s3backer",' '.join(pp_list),container,path]), shell=True)    
    '''
    taskset -c core s3backer \
                    --baseURL= \
                    --accessId= \ 
                    --accessKey= \
                    --listBlocks \
                    --blockSize= \
                    --size= \
                    --blockCacheSize= \
                    --blockCacheThreads= \
                    ontaine path

                    #--debug
    '''

    return


def loop_map(pv,loop_num):
    loop_dev="/dev/loop"+str(loop_num)
    raw_file="/srv/"+pv+"/file" 
    subprocess.call(["losetup", loop_dev, raw_file])
    
    return loop_dev



def lvm_pv_binding(dev):
    '''pvcreate /dev/a /dev/b'''
    subprocess.call(["pvcreate", dev])
    

def lvm_vg_binding(vg,pvs):
    '''
    vgcreate -s %PE_SIZE %VG_NAME &PV_list
    vg - specified volume group
    pvs - a list of pv
    '''
    PE_SIZE="128M"
    VG_NAME=vg
    subprocess.call([' '.join(["vgcreate","-s",PE_SIZE,VG_NAME,' '.join(pvs)])],shell=True)
    return

    
