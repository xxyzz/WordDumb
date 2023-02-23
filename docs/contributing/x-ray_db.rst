Kindle X-Ray database
=====================

XRAY.entities.ASIN.asc
----------------------

Android app path: `/sdcard/Android/data/com.amazon.kindle/files/ASIN/XRAY.ASIN.acr.db`

book_metadata
^^^^^^^^^^^^^

+-------+--------+------------+--------------+-----------------------+------------+-----------+------------+----------------+
| srl   | erl    | has_images | has_excerpts | show_spoilers_default | num_people | num_terms | num_images | preview_images |
+=======+========+============+==============+=======================+============+===========+============+================+
| 15118 | 911699 | 0          | 1            | 1                     | 83         | 177       | 0          |                |
+-------+--------+------------+--------------+-----------------------+------------+-----------+------------+----------------+

.. code-block:: console

   sqlite> .schema book_metadata
   CREATE TABLE book_metadata(srl INTEGER, erl INTEGER, has_images TINYINT, has_excerpts TINYINT, show_spoilers_default TINYINT, num_people INTEGER, num_terms INTEGER, num_images INTEGER, preview_images TEXT);

srl: start reading location, where a new book should open for the first time

erl: end reading location, where 'before you go' page shows

preview_images: excerpt ids of images joined by ','

bookmentions_entity
^^^^^^^^^^^^^^^^^^^

+----+------------+------------------------+------------------------+----------------+------------------+--------------+-------------+
| id | asin       | title                  | authors                | description    | ratings          | totalRatings | type        |
+====+============+========================+========================+================+==================+==============+=============+
| 0  | B003LY486E | Process and Reality... | Alfred North Whitehead | One of the ... | 4.59999990463257 | 60           | ABIS_EBOOKS |
+----+------------+------------------------+------------------------+----------------+------------------+--------------+-------------+

bookmentions_occurrence
^^^^^^^^^^^^^^^^^^^^^^^

======== ======== ======== 
 entity   start    length  
======== ======== ======== 
 0        168413   19      
 0        168990   37      
 0        923504   19      
======== ======== ======== 

entity
^^^^^^

==== ====================== =========== ====== ======= =============== 
 id   label                  loc_label   type   count   has_info_card  
==== ====================== =========== ====== ======= =============== 
 0                           1                          0              
 1    Henry Norris Russell               1      4       1              
 2    Jim Baker                          1      5       1              
 3    Havana                             2      3       1              
 4    Gweneth                            1      6       1              
==== ====================== =========== ====== ======= =============== 

entity_description
^^^^^^^^^^^^^^^^^^

+-------------------------+----------------------+--------+--------+
| text                    | source_wildcard      | source | entity |
+=========================+======================+========+========+
| Henry Norris Russell... | Henry Norris Russell | 1      | 1      |
+-------------------------+----------------------+--------+--------+

If text is from the book the source is null.

entity_excerpt
^^^^^^^^^^^^^^

======== ========= 
 entity   excerpt  
======== ========= 
 0        0        
 57       0        
 57       1        
 43       2        
 153      2        
======== =========

excerpt
^^^^^^^

notable clips

==== ======= ======== ======= ============================================== ====== 
 id   start   length   image   related_entities                               goto  
==== ======= ======== ======= ============================================== ====== 
 0    15283   424              57                                                   
 1    16340   948              57,66                                                
 2    18638   463              153,164,46,43,54,62,186,57,66,37,98,110,21,4         
 3    25976   585              259                                                  
 4    27980   435              29,161,94,54                                         
==== ======= ======== ======= ============================================== ====== 

MOBI image:

===== ======== ======== ================================== ================== ======== 
 id    start    length   image                              related_entities   goto    
===== ======== ======== ================================== ================== ======== 
 179   690      0        kindle:embed:0007?mime=image/jpg                      690     
 180   386520   1390     kindle:embed:0008?mime=image/jpg                      386400  
===== ======== ======== ================================== ================== ======== 

image: `src` attribute of `<img>`

goto: `<img>` tag byte offsets

start: byte offsets of the next sentence below the image

length: byte length of the sentence

KFX image:

===== ========= ======== ======= ================== ========= 
 id    start     length   image   related_entities   goto     
===== ========= ======== ======= ================== ========= 
 576   1         0        e6                         1        
 577   2179585   71       e2GX                       2179583  
===== ========= ======== ======= ================== ========= 

image: KFX resources identifier

occurrence
^^^^^^^^^^

all mentions

======== ======== ======== 
 entity   start    length  
======== ======== ======== 
 1        193800   7       
 1        192950   7       
 1        924367   8       
 1        192977   21      
 2        333035   10      
======== ======== ======== 

source
^^^^^^

==== ======= ===== =============== ============= 
 id   label   url   license_label   license_url  
==== ======= ===== =============== ============= 
 0    5       20                                 
 1    6       21    7               8            
 2    4       22                                 
==== ======= ===== =============== ============= 

id 0: Kindle Store

id 1: Wikipedia

other columns are ids of the string table

string
^^^^^^

==== ========== ====== 
 id   language   text  
==== ========== ====== 
 0    de         Alle  
 0    en         All   
 0    en-AU      All   
 0    en-CA      All   
 0    en-IN      All   
==== ========== ====== 

type
^^^^

==== ======= ================ ====== ================================= 
 id   label   singular_label   icon   top_mentioned_entities           
==== ======= ================ ====== ================================= 
 1    14      15               1      57,71,93,39,12,30,117,18,63,107  
 2    16      17               2      164,66,153,46,37,43,5,111,54,9   
==== ======= ================ ====== ================================= 

type 1: people, type 2: terms

PRAGMA user_version = 1
^^^^^^^^^^^^^^^^^^^^^^^

Checked at `com.amazon.ebook.booklet.reader.plugin.xray.db.SidecarDatabaseAdapter` (/opt/amazon/ebook/lib/Xray.jar).
