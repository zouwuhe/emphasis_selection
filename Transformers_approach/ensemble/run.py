
import codecs
import numpy as np

def read_map(file, map):
  
  with codecs.open(file, 'r', 'utf-8') as f:
      lines = f.readlines()

  flag = True

  d = [[]]

  i = 0
  
  for line in lines:
    if not (line.isspace()):
      feats = line.strip().split()
      d.append(feats)
      flag = False
    
    elif flag == False:
      d.pop(0)
      map[i] = d
      # print(d)
      i = i + 1
      flag = True
      d = [[]]
    
  # print(i)

def intersection(lst1, lst2):
    lst3 = [value for value in lst1 if value in lst2]
    return lst3

def match_M(batch_scores_no_padd, batch_labels_no_pad):

    top_m = [1, 2, 3, 4]
    batch_num_m=[]
    batch_score_m=[]
    for m in top_m:
        intersects_lst = []
        # exact_lst = []
        score_lst = []
        ############################################### computing scores:
        for s in batch_scores_no_padd:
            if len(s) <=m:
                continue
            h = m
            # if len(s) > h:
            #     while (s[np.argsort(s)[-h]] == s[np.argsort(s)[-(h + 1)]] and h < (len(s) - 1)):
            #         h += 1

            # s = np.asarray(s.cpu())
            s = np.asarray(s)
            #ind_score = np.argsort(s)[-h:]
            ind_score = sorted(range(len(s)), key = lambda sub: s[sub])[-h:]
            score_lst.append(ind_score)

        ############################################### computing labels:
        label_lst = []
        for l in batch_labels_no_pad:
            if len(l) <=m:
                continue
            # if it contains several top values with the same amount
            h = m
            # l = l.cpu()
            if len(l) > h:
                while (l[np.argsort(l)[-h]] == l[np.argsort(l)[-(h + 1)]] and h < (len(l) - 1)):
                    h += 1
            l = np.asarray(l)
            ind_label = np.argsort(l)[-h:]
            label_lst.append(ind_label)

        ############################################### :

        for i in range(len(score_lst)):
            intersect = intersection(score_lst[i], label_lst[i])
            intersects_lst.append((len(intersect))/(min(m, len(score_lst[i]))))
            # sorted_score_lst = sorted(score_lst[i])
            # sorted_label_lst =  sorted(label_lst[i])
            # if sorted_score_lst==sorted_label_lst:
            #     exact_lst.append(1)
            # else:
            #     exact_lst.append(0)
        batch_num_m.append(len(score_lst))
        batch_score_m.append(sum(intersects_lst))
    return batch_num_m, batch_score_m

def print_to_file(save_path,file_path, var):
  with open(save_path + file_path, "w") as text_file:
    text_file.write(var)

# from google.colab import drive
# drive.mount('/content/drive', force_remount=True)

dir_path = 'drive/My Drive/datasets/ensemble/'

bert_path = dir_path + 'bert_Model/'
bertmaskedLM_path = dir_path + 'bert_maskedLM/'
roberta_path = dir_path + 'roberta_large/all/'
roberta_high = dir_path + 'roberta_large/top3/'
xlnet_path = dir_path + 'xlnet/xlnet_900_40/'
xlnet_all = dir_path + 'xlnet/all/'
xlnet_high = dir_path + 'xlnet/top/'
test_path = dir_path + 'test_mix/'

cur_path = test_path
save_path = cur_path

val_length = 392
test_length = 743

n = 13

# ind = ["" for x in range(n)]
val_list = ["" for x in range(n)]
test_list = ["" for x in range(n)]

## bert
n1 = 2
ind1 = [3,4]

## roberta
n2 = 3
# ind2 = [1,2,3,4,5,6,7,8,9]
ind2 = [5,7,8]

## xlnet
n3 = 8
# ind3 = [1,2,3,4,7,8,9,10,11]
ind3 = [1,2,3,4,5,6,7,8]

for i in range(n1):
  # ind[i] = "bert/" + ind1[i]
  val_list[i] = cur_path + 'bert/val' + str(ind1[i]) + '.txt'
  test_list[i] = cur_path + 'bert/test' + str(ind1[i]) + '.txt'

for i in range(n2):
  # ind[n1+i] = "roberta/" + ind2[i]
  val_list[n1+i] = cur_path + 'roberta/val' + str(ind2[i]) + '.txt'
  test_list[n1+i] = cur_path + 'roberta/test' + str(ind2[i]) + '.txt'

for i in range(n3):
  # ind[n1+n2+i] = str(i+1)
  val_list[n1+n2+i] = cur_path + 'xlnet/val' + str(ind3[i]) + '.txt'
  test_list[n1+n2+i] = cur_path + 'xlnet/test' + str(ind3[i]) + '.txt'

vdict_list = [dict() for x in range(n)]
tdict_list = [dict() for x in range(n)]

for i in range(n):
  print("")
  # print(i)
  # val_list[i] = cur_path + 'val' + str(index) + '.txt'
  # test_list[i] = cur_path + 'test' + str(index) + '.txt'
  print(val_list[i])
  read_map(val_list[i], vdict_list[i])
  read_map(test_list[i], tdict_list[i])

## VALIDATION CHECK

num_m = [0, 0, 0, 0]
score_m = [0, 0, 0, 0]

cnt = 0

all_labels = []
all_our_labels = []

dict_list = vdict_list

dummy = dict_list[0]

# temp = True

for i in range(val_length):
  # d1 = vdict_list[1][i]
  d1 = dummy[i]
  # print(d1)

  labels = []
  our_labels = []

  for j in range(len(d1)):
    # print(d1[j])
    label = (float)(d1[j][3])
    labels.append(label)
    ls = [0.0 for x in range(n)]
    for k in range(n):
      d = dict_list[k][i][j]
      # print(d)
      ls[k] = (float)(d[2])
      # if temp == True:
      #   print(d[1])
    
    # our_label1 = (float)(d1[j][2])
    # our_label2 = (float)(d2[j][2])
    # ls = [our_label1, our_label2]
    # ls.pop(0)
    our_label = np.mean(ls)
    # if temp == True:
    #   print(ls)
    #   print(our_label)
    #   temp = False
    our_labels.append(our_label)
    # print(type(d1[j][2]))
    # break

  # print(labels)
  # print(our_labels)

  cnt = cnt + 1
  all_labels.append(labels)
  all_our_labels.append(our_labels)

  if cnt%1==0:
    # nlabels = np.array(labels).reshape(1,len(labels))
    # nour_labels = np.array(our_labels).reshape(1,len(our_labels))

    # print(all_labels)

    batch_num_m, batch_score_m = match_M(all_our_labels, all_labels)

    num_m = [sum(i) for i in zip(num_m, batch_num_m)]
    # print(num_m)
    score_m = [sum(i) for i in zip(score_m, batch_score_m)]
    # print(score_m)

    all_labels = []
    all_our_labels = []

  # print (d1)
  # print (d2)
  # break

m_score = [i/j for i,j in zip(score_m, num_m)]

print(m_score)
v_score = np.mean(m_score)
print(v_score)

## TEST OUTPUT

s = ""
sent_id = ""
k = 0

dict_list = tdict_list
dummy = dict_list[0]

for i in range(test_length):
  d1 = dummy[i]
  # d1 = td1[i]
  # d2 = td2[i]

  our_labels = []

  s = s + "\n"

  for j in range(len(d1)):
    ls = [0.0 for x in range(n)]
    for k in range(n):
      d = dict_list[k][i][j]
      # print(d)
      ls[k] = (float)(d[2])
    # our_label1 = (float)(d1[j][2])
    # our_label2 = (float)(d2[j][2])
    # ls = [our_label1, our_label2]
    # print(ls)
    our_label = np.mean(ls)

    s = s + "{}\t{}\t{}\t".format(d1[j][0],d1[j][1],our_label) + "\n"
  
  # s = s + "\n"

file_name = 'bert_2_roberta_3_xlnet_8.txt'
print_to_file(save_path, file_name, s)
print_to_file(save_path, 'acc_'+file_name, str(v_score)+"\n"+str(m_score))
