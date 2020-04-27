

train_file = 'drive/My Drive/datasets/train.txt'
dev_file = 'drive/My Drive/datasets/dev.txt'
emb_file = 'drive/My Drive/datasets/glove.6B.100d.txt'


from collections import Counter
import codecs
import itertools
from functools import reduce
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.init
from torch.nn.utils.rnn import pack_padded_sequence
import torch.utils.data as data_utils
import time
from allennlp.modules.elmo import Elmo, batch_to_ids
from torch.nn.utils.rnn import pack_padded_sequence, pad_packed_sequence
from config import *
#from torchsummary import summary

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(device)

def read_words_tags(file, word_ind, tag_ind, prob_ind, caseless=True):
    
    with codecs.open(file, 'r', 'utf-8') as f:
        lines = f.readlines()
    #print(lines)
    words = []
    tags = []
    probs = []
    temp_w = []
    temp_t = []
    temp_p = []
    
    for line in lines:
        if not (line.isspace()):
            feats = line.strip().split()
            temp_w.append(feats[word_ind].lower() if caseless else feats[word_ind])
            temp_t.append(feats[tag_ind])
            temp_p.append((float)(feats[prob_ind]))
        elif len(temp_w) > 0:
            assert len(temp_w) == len(temp_t)
            words.append(temp_w)
            tags.append(temp_t)
            probs.append(temp_p)
            temp_w = []
            temp_t = []
            temp_p = []
            
    if len(temp_w) > 0:
        assert len(temp_w) == len(temp_t)
        words.append(temp_w)
        tags.append(temp_t)
        probs.append(temp_p)
            
    assert len(words) == len(tags) == len(probs)
    #print(probs)
    
    return words, tags, probs

# train_file = "train.txt"
# dev_file = "dev.txt"

word_index = 1
tag_index = 5
prob_index = 4

caseless=True

t_words , t_tags , t_probs = read_words_tags(train_file,word_index,tag_index,prob_index,caseless)
#for i in range(len(t_words)):
#    t_words[i] = [i + j for i, j in zip(t_words[i], t_tags[i])]
d_words , d_tags , d_probs = read_words_tags(dev_file,word_index,tag_index,prob_index,caseless)
#for i in range(len(d_words)):
#    d_words[i] = [i + j for i, j in zip(d_words[i], d_tags[i])]

print(t_probs)

def create_maps(words, tags, min_word_freq=5, min_char_freq=1):
    
    word_freq = Counter()
    char_freq = Counter()
    tag_map = set()
    for w, t in zip(words, tags):
        word_freq.update(w)
        char_freq.update(list(reduce(lambda x, y: list(x) + [' '] + list(y), w)))
        tag_map.update(t)
    #print(word_freq)
    
    word_map = {k: v + 1 for v, k in enumerate([w for w in word_freq.keys() if word_freq[w] > min_word_freq])}
    char_map = {k: v + 1 for v, k in enumerate([c for c in char_freq.keys() if char_freq[c] > min_char_freq])}
    tag_map = {k: v + 1 for v, k in enumerate(tag_map)}

    word_map['<pad>'] = 0
    word_map['<end>'] = len(word_map)
    word_map['<unk>'] = len(word_map)
    char_map['<pad>'] = 0
    char_map['<end>'] = len(char_map)
    char_map['<unk>'] = len(char_map)
    tag_map['<pad>'] = 0
    tag_map['<start>'] = len(tag_map)
    tag_map['<end>'] = len(tag_map)
    #print(word_map)
    
    return word_map, char_map, tag_map

min_word_freq=1
min_char_freq=1

word_map, char_map, tag_map = create_maps(t_words+d_words,t_tags+d_tags,min_word_freq, min_char_freq)

print(type(word_map))

def create_input_tensors(words, tags, probs, word_map, char_map, tag_map):
   
    # Encode sentences into word maps with <end> at the end
    # [['dunston', 'checks', 'in', '<end>']] -> [[4670, 4670, 185, 4669]]
    wmaps = list(map(lambda s: list(map(lambda w: word_map.get(w, word_map['<unk>']), s)) + [word_map['<end>']], words))

    # Forward and backward character streams
    # [['d', 'u', 'n', 's', 't', 'o', 'n', ' ', 'c', 'h', 'e', 'c', 'k', 's', ' ', 'i', 'n', ' ']]
    chars_f = list(map(lambda s: list(reduce(lambda x, y: list(x) + [' '] + list(y), s)) + [' '], words))
    # [['n', 'i', ' ', 's', 'k', 'c', 'e', 'h', 'c', ' ', 'n', 'o', 't', 's', 'n', 'u', 'd', ' ']]
    chars_b = list(
        map(lambda s: list(reversed([' '] + list(reduce(lambda x, y: list(x) + [' '] + list(y), s)))), words))

    # Encode streams into forward and backward character maps with <end> at the end
    # [[29, 2, 12, 8, 7, 14, 12, 3, 6, 18, 1, 6, 21, 8, 3, 17, 12, 3, 60]]
    cmaps_f = list(
        map(lambda s: list(map(lambda c: char_map.get(c, char_map['<unk>']), s)) + [char_map['<end>']], chars_f))
    # [[12, 17, 3, 8, 21, 6, 1, 18, 6, 3, 12, 14, 7, 8, 12, 2, 29, 3, 60]]
    cmaps_b = list(
        map(lambda s: list(map(lambda c: char_map.get(c, char_map['<unk>']), s)) + [char_map['<end>']], chars_b))

    # Positions of spaces and <end> character
    # Words are predicted or encoded at these places in the language and tagging models respectively
    # [[7, 14, 17, 18]] are points after '...dunston', '...checks', '...in', '...<end>' respectively
    cmarkers_f = list(map(lambda s: [ind for ind in range(len(s)) if s[ind] == char_map[' ']] + [len(s) - 1], cmaps_f))
    # Reverse the markers for the backward stream before adding <end>, so the words of the f and b markers coincide
    # i.e., [[17, 9, 2, 18]] are points after '...notsnud', '...skcehc', '...ni', '...<end>' respectively
    cmarkers_b = list(
        map(lambda s: list(reversed([ind for ind in range(len(s)) if s[ind] == char_map[' ']])) + [len(s) - 1],
            cmaps_b))

    # Encode tags into tag maps with <end> at the end
    tmaps = list(map(lambda s: list(map(lambda t: tag_map[t], s)) + [tag_map['<end>']], tags))
    
    # Since we're using CRF scores of size (prev_tags, cur_tags), find indices of target sequence in the unrolled scores
    # This will be row_index (i.e. prev_tag) * n_columns (i.e. tagset_size) + column_index (i.e. cur_tag)
    #tmaps = list(map(lambda s: [tag_map['<start>'] * len(tag_map) + s[0]] + [s[i - 1] * len(tag_map) + s[i] for i in range(1, len(s))], tmaps))
    # Note - the actual tag indices can be recovered with tmaps % len(tag_map)

    # Pad, because need fixed length to be passed around by DataLoaders and other layers
    word_pad_len = max(list(map(lambda s: len(s), wmaps)))
    char_pad_len = max(list(map(lambda s: len(s), cmaps_f)))

    # Sanity check
    assert word_pad_len == max(list(map(lambda s: len(s), tmaps)))

    padded_wmaps = []
    padded_cmaps_f = []
    padded_cmaps_b = []
    padded_cmarkers_f = []
    padded_cmarkers_b = []
    padded_tmaps = []
    wmap_lengths = []
    cmap_lengths = []
    padded_probs = []

    for word, w, cf, cb, cmf, cmb, t,p in zip(words, wmaps, cmaps_f, cmaps_b, cmarkers_f, cmarkers_b, tmaps,probs):
        # Sanity  checks
        assert len(w) == len(cmf) == len(cmb) == len(t)
        assert len(cmaps_f) == len(cmaps_b)

        # Pad
        # A note -  it doesn't really matter what we pad with, as long as it's a valid index
        # i.e., we'll extract output at those pad points (to extract equal lengths), but never use them

        padded_wmaps.append(w + [word_map['<pad>']] * (word_pad_len - len(w)))
        padded_cmaps_f.append(cf + [char_map['<pad>']] * (char_pad_len - len(cf)))
        padded_cmaps_b.append(cb + [char_map['<pad>']] * (char_pad_len - len(cb)))

        # 0 is always a valid index to pad markers with (-1 is too but torch.gather has some issues with it)
        padded_cmarkers_f.append(cmf + [0] * (word_pad_len - len(w)))
        padded_cmarkers_b.append(cmb + [0] * (word_pad_len - len(w)))

        padded_tmaps.append(t + [tag_map['<pad>']] * (word_pad_len - len(t)))
        padded_probs.append(p + [0] * (word_pad_len - len(p)))

        
        wmap_lengths.append(len(w))
        cmap_lengths.append(len(cf))

        # Sanity check
        assert len(padded_wmaps[-1]) == len(padded_tmaps[-1]) == len(padded_cmarkers_f[-1]) == len(
            padded_cmarkers_b[-1]) == word_pad_len == len(padded_probs[-1])
        assert len(padded_cmaps_f[-1]) == len(padded_cmaps_b[-1]) == char_pad_len

    padded_wmaps = torch.LongTensor(padded_wmaps)
    padded_cmaps_f = torch.LongTensor(padded_cmaps_f)
    padded_cmaps_b = torch.LongTensor(padded_cmaps_b)
    padded_cmarkers_f = torch.LongTensor(padded_cmarkers_f)
    padded_cmarkers_b = torch.LongTensor(padded_cmarkers_b)
    padded_tmaps = torch.LongTensor(padded_tmaps)
    wmap_lengths = torch.LongTensor(wmap_lengths)
    cmap_lengths = torch.LongTensor(cmap_lengths)
    padded_probs = torch.FloatTensor(padded_probs)
    
    return padded_wmaps, padded_cmaps_f, padded_cmaps_b, padded_cmarkers_f, padded_cmarkers_b, padded_tmaps, wmap_lengths, cmap_lengths , padded_probs

batch_size = 10
workers = 1

padded_wmaps, padded_cmaps_f, padded_cmaps_b, padded_cmarkers_f, padded_cmarkers_b, padded_tmaps, wmap_lengths, cmap_lengths , padded_probs = create_input_tensors(t_words, t_tags,t_probs, word_map, char_map, tag_map)


t_inputs = data_utils.TensorDataset( padded_wmaps, padded_cmaps_f, padded_cmaps_b, padded_cmarkers_f, padded_cmarkers_b, padded_tmaps, wmap_lengths, cmap_lengths , padded_probs)
train_loader = torch.utils.data.DataLoader(t_inputs, batch_size = batch_size, shuffle=True, num_workers=workers, pin_memory=False)

padded_wmaps, padded_cmaps_f, padded_cmaps_b, padded_cmarkers_f, padded_cmarkers_b, padded_tmaps, wmap_lengths, cmap_lengths , padded_probs = create_input_tensors(d_words, d_tags,d_probs, word_map, char_map, tag_map)
d_inputs = data_utils.TensorDataset( padded_wmaps, padded_cmaps_f, padded_cmaps_b, padded_cmarkers_f, padded_cmarkers_b, padded_tmaps, wmap_lengths, cmap_lengths , padded_probs)
val_loader = torch.utils.data.DataLoader(d_inputs, batch_size = batch_size, shuffle=True, num_workers=workers, pin_memory=False)

def init_embedding(input_embedding):
    """
    Initialize embedding tensor with values from the uniform distribution.
    :param input_embedding: embedding tensor
    :return:
    """
    bias = np.sqrt(3.0 / input_embedding.size(1))
    nn.init.uniform_(input_embedding, -bias, bias)

def load_embeddings(emb_file, word_map, expand_vocab=True):
    """
    Load pre-trained embeddings for words in the word map.
    :param emb_file: file with pre-trained embeddings (in the GloVe format)
    :param word_map: word map
    :param expand_vocab: expand vocabulary of word map to vocabulary of pre-trained embeddings?
    :return: embeddings for words in word map, (possibly expanded) word map,
            number of words in word map that are in-corpus (subject to word frequency threshold)
    """
    with open(emb_file, 'r') as f:
        emb_len = len(f.readline().split(' ')) - 1

    print("Embedding length is %d." % emb_len)

    # Create tensor to hold embeddings for words that are in-corpus
    ic_embs = torch.FloatTensor(len(word_map), emb_len)
    init_embedding(ic_embs)

    if expand_vocab:
        print("You have elected to include embeddings that are out-of-corpus.")
        ooc_words = []
        ooc_embs = []
    else:
        print("You have elected NOT to include embeddings that are out-of-corpus.")

    # Read embedding file
    print("\nLoading embeddings...")
    for line in open(emb_file, 'r',encoding="utf8"):
        line = line.split(' ')
        emb_word = line[0]
        embedding = list(map(lambda t: float(t), filter(lambda n: n and not n.isspace(), line[1:])))

        if not expand_vocab and emb_word not in word_map:
            continue

        # If word is in train_vocab, store at the correct index (as in the word_map)
        if emb_word in word_map:
            ic_embs[word_map[emb_word]] = torch.FloatTensor(embedding)

        # If word is in dev or test vocab, store it and its embedding into lists
        elif expand_vocab:
            ooc_words.append(emb_word)
            ooc_embs.append(embedding)

    lm_vocab_size = len(word_map)  # keep track of lang. model's output vocab size (no out-of-corpus words)

    if expand_vocab:
        print("'word_map' is being updated accordingly.")
        for word in ooc_words:
            word_map[word] = len(word_map)
        ooc_embs = torch.FloatTensor(np.asarray(ooc_embs))
        embeddings = torch.cat([ic_embs, ooc_embs], 0)

    else:
        embeddings = ic_embs

    # Sanity check
    assert embeddings.size(0) == len(word_map)

    print("\nDone.\n Embedding vocabulary: %d\n Language Model vocabulary: %d.\n" % (len(word_map), lm_vocab_size))

    return embeddings, word_map, lm_vocab_size

#emb_file = glove_100
expand_vocab = False
word_emb_dim = 2048
options_file = "https://s3-us-west-2.amazonaws.com/allennlp/models/elmo/2x4096_512_2048cnn_2xhighway/elmo_2x4096_512_2048cnn_2xhighway_options.json"
weight_file = "https://s3-us-west-2.amazonaws.com/allennlp/models/elmo/2x4096_512_2048cnn_2xhighway/elmo_2x4096_512_2048cnn_2xhighway_weights.hdf5"
embeddings, word_map, lm_vocab_size = load_embeddings(emb_file, word_map,expand_vocab)

print(embeddings.size())
print(lm_vocab_size)

class ElmoLayer(nn.Module):
    def __init__(self,options_file, weight_file):
        super(ElmoLayer, self).__init__()
        self.elmo = Elmo(options_file, weight_file, 2, dropout=0.3)



    def forward(self, words):
        character_ids = batch_to_ids(words)
        character_ids = character_ids.to(device)
        elmo_output = self.elmo(character_ids)
        elmo_representation = torch.cat(elmo_output['elmo_representations'], -1)
        #mask = elmo_output['mask']
        elmo_representation.to(device)
        if torch.cuda.is_available():
            elmo_representation = elmo_representation.cuda()
            #mask = mask.cuda()
        return elmo_representation #, mask
    
class Attention(nn.Module):
    """Attention mechanism written by Gustavo Aguilar https://github.com/gaguilar"""
    def __init__(self,  hidden_size):
        super(Attention, self).__init__()
        self.da = hidden_size
        self.dh = hidden_size

        self.W = nn.Linear(self.dh, self.da)        # (feat_dim, attn_dim)
        self.v = nn.Linear(self.da, 1)              # (attn_dim, 1)

    def forward(self, inputs, mask):
        # Raw scores
        u = self.v(torch.tanh(self.W(inputs)))      # (batch, seq, hidden) -> (batch, seq, attn) -> (batch, seq, 1)

        # Masked softmax
        u = u.exp()                                 # exp to calculate softmax
        u = mask.unsqueeze(2).float().to(device) * u           # (batch, seq, 1) * (batch, seq, 1) to zerout out-of-mask numbers
        sums = torch.sum(u, dim=1, keepdim=True)    # now we are sure only in-mask values are in sum
        a = u / sums                                # the probability distribution only goes to in-mask values now

        # Weighted vectors
        z = inputs * a

        return  z,  a.view(inputs.size(0), inputs.size(1))

class Highway(nn.Module):
    """
    Highway Network.
    """

    def __init__(self, size, num_layers=1, dropout=0.5):
        """
        :param size: size of linear layer (matches input size)
        :param num_layers: number of transform and gate layers
        :param dropout: dropout
        """
        super(Highway, self).__init__()
        self.size = size
        self.num_layers = num_layers
        self.transform = nn.ModuleList()  # list of transform layers
        self.gate = nn.ModuleList()  # list of gate layers
        self.dropout = nn.Dropout(p=dropout)

        for i in range(num_layers):
            transform = nn.Linear(size, size)
            gate = nn.Linear(size, size)
            self.transform.append(transform)
            self.gate.append(gate)

    def forward(self, x):
        """
        Forward propagation.
        :param x: input tensor
        :return: output tensor, with same dimensions as input tensor
        """
        transformed = nn.functional.relu(self.transform[0](x))  # transform input
        g = nn.functional.sigmoid(self.gate[0](x))  # calculate how much of the transformed input to keep

        out = g * transformed + (1 - g) * x  # combine input and transformed input in this ratio

        # If there are additional layers
        for i in range(1, self.num_layers):
            out = self.dropout(out)
            transformed = nn.functional.relu(self.transform[i](out))
            g = nn.functional.sigmoid(self.gate[i](out))

            out = g * transformed + (1 - g) * out

        return out
    
class LM_LSTM_CRF(nn.Module):

    def __init__(self, charset_size, char_emb_dim, char_rnn_dim, char_rnn_layers,
                 lm_vocab_size, word_emb_dim, word_rnn_dim, word_rnn_layers, dropout, highway_layers=1):
        
        super(LM_LSTM_CRF, self).__init__()

        self.target_size = target_size  # this is the size of the output vocab of the tagging model
        self.hidden_size = hidden_size
        
        self.charset_size = charset_size
        self.char_emb_dim = char_emb_dim
        self.char_rnn_dim = char_rnn_dim
        self.char_rnn_layers = char_rnn_layers
        

        self.wordset_size = lm_vocab_size  # this is the size of the input vocab (embedding layer) of the tagging model
        self.word_emb_dim = word_emb_dim
        self.word_rnn_dim = word_rnn_dim
        self.word_rnn_layers = word_rnn_layers
        
        self.highway_layers = highway_layers

        self.dropout = nn.Dropout(p=dropout)
        
        self.char_embeds = nn.Embedding(self.charset_size, self.char_emb_dim)  # character embedding layer
        self.forw_char_lstm = nn.LSTM(self.char_emb_dim, self.char_rnn_dim, num_layers=self.char_rnn_layers,
                                      bidirectional=False, dropout=dropout)  # forward character LSTM
        self.back_char_lstm = nn.LSTM(self.char_emb_dim, self.char_rnn_dim, num_layers=self.char_rnn_layers,
                                      bidirectional=False, dropout=dropout)  # backward character LSTM

        self.subword_hw = Highway(2 * self.char_rnn_dim, num_layers=self.highway_layers,
                                  dropout=dropout).to(device)  # highway to transform combined forward and backward char LSTM outputs for use in the word BLSTM

        self.word_embeds = nn.Embedding(self.wordset_size, self.word_emb_dim)  # word embedding layer
        self.elmo = ElmoLayer(options_file, weight_file)
        self.word_blstm = nn.LSTM(self.word_emb_dim + self.char_rnn_dim * 2, self.word_rnn_dim, num_layers=self.word_rnn_layers, bidirectional=True, dropout=dropout)  # word BLSTM
        


        self.attention = Attention(self.word_rnn_dim*2).to(device)
        
        self.fc1 = nn.Linear((self.word_rnn_dim*2)+1, self.hidden_size) 
        #self.fc1 = nn.Linear((self.word_rnn_dim*2), self.hidden_size)  
        self.fc2 = nn.Linear(self.hidden_size, self.target_size)
        
    def init_word_embeddings(self, embeddings):
        """
        Initialize embeddings with pre-trained embeddings.
        :param embeddings: pre-trained embeddings
        """
        self.word_embeds.weight = nn.Parameter(embeddings)

    def fine_tune_word_embeddings(self, fine_tune=False):
        """
        Fine-tune embedding layer? (Not fine-tuning only makes sense if using pre-trained embeddings).
        :param fine_tune: Fine-tune?
        """
        for p in self.word_embeds.parameters():
            p.requires_grad = fine_tune

    def forward(self, words, cmaps_f, cmaps_b, cmarkers_f, cmarkers_b, wmaps, wmap_lengths, cmap_lengths, probs, tmaps):
        
        self.batch_size = cmaps_f.size(0)
        self.word_pad_len = wmaps.size(1)

        # Sort by decreasing true char. sequence length
        cmap_lengths, char_sort_ind = cmap_lengths.sort(dim=0, descending=True)
        cmaps_f = cmaps_f[char_sort_ind]
        cmaps_b = cmaps_b[char_sort_ind]
        cmarkers_f = cmarkers_f[char_sort_ind]
        cmarkers_b = cmarkers_b[char_sort_ind]
        wmaps = wmaps[char_sort_ind]
        tmaps = tmaps[char_sort_ind]
        wmap_lengths = wmap_lengths[char_sort_ind]
        probs = probs[char_sort_ind]
        char_order = char_sort_ind.tolist()
        words_char_sorted = []
        for i in range(len(char_order)):
            words_char_sorted.append(words[char_order[i]])
        # Embedding look-up for characters
        cf = self.char_embeds(cmaps_f.to(device))  # (batch_size, char_pad_len, char_emb_dim)
        cb = self.char_embeds(cmaps_b.to(device))

        # Dropout
        cf = self.dropout(cf)  # (batch_size, char_pad_len, char_emb_dim)
        cb = self.dropout(cb)

        # Pack padded sequence
        cf = pack_padded_sequence(cf, cmap_lengths.tolist(),
                                  batch_first=True)  # packed sequence of char_emb_dim, with real sequence lengths
        cb = pack_padded_sequence(cb, cmap_lengths.tolist(), batch_first=True)

        # LSTM
        cf, _ = self.forw_char_lstm(cf)  # packed sequence of char_rnn_dim, with real sequence lengths
        cb, _ = self.back_char_lstm(cb)

        # Unpack packed sequence
        cf, _ = pad_packed_sequence(cf, batch_first=True)  # (batch_size, max_char_len_in_batch, char_rnn_dim)
        cb, _ = pad_packed_sequence(cb, batch_first=True)

        # Sanity check
        assert cf.size(1) == max(cmap_lengths.tolist()) == list(cmap_lengths)[0]
        
        
        # Select RNN outputs only at marker points (spaces in the character sequence)
        cmarkers_f = cmarkers_f.unsqueeze(2).expand(self.batch_size, self.word_pad_len, self.char_rnn_dim)
        cmarkers_b = cmarkers_b.unsqueeze(2).expand(self.batch_size, self.word_pad_len, self.char_rnn_dim)
        cf_selected = torch.gather(cf, 1, cmarkers_f)  # (batch_size, word_pad_len, char_rnn_dim)
        cb_selected = torch.gather(cb, 1, cmarkers_b)


        # Sort by decreasing true word sequence length
        wmap_lengths, word_sort_ind = wmap_lengths.sort(dim=0, descending=True)
        wmaps = wmaps[word_sort_ind]
        probs = probs[word_sort_ind]
        tmaps = tmaps[word_sort_ind]
        cf_selected = cf_selected[word_sort_ind]  # for language model
        cb_selected = cb_selected[word_sort_ind]
        word_order = word_sort_ind.tolist()
        words_word_sorted = []
        for i in range(len(word_order)):
            words_word_sorted.append(words_char_sorted[word_order[i]])
        # Embedding look-up for words
       # w = self.word_embeds(wmaps)  # (batch_size, word_pad_len, word_emb_dim)
        #w = self.dropout(w)
        w = self.elmo(words_word_sorted)
        
        
        # Sub-word information at each word
        subword = self.subword_hw(self.dropout(
            torch.cat((cf_selected, cb_selected), dim=2)))  # (batch_size, word_pad_len, 2 * char_rnn_dim)
        
        
        subword = self.dropout(subword)
        
        # Concatenate word embeddings and sub-word features
        w = torch.cat((w, subword), dim=2)  # (batch_size, word_pad_len, word_emb_dim + 2 * char_rnn_dim)

        # Pack padded sequence
        w = pack_padded_sequence(w, list(wmap_lengths), batch_first=True)  # packed sequence of word_emb_dim + 2 * char_rnn_dim, with real sequence lengths
        
        # LSTM
        w, _ = self.word_blstm(w)  # packed sequence of word_rnn_dim, with real sequence lengths

        # Unpack packed sequence
        w, _ = pad_packed_sequence(w, batch_first=True)  # (batch_size, max_word_len_in_batch, word_rnn_dim)
        w = self.dropout(w)
        
        mask = []
        for i in range(len(wmap_lengths)):
            mask_row = (np.concatenate([np.ones(wmap_lengths[i]),np.zeros(len(wmaps[i])-wmap_lengths[i])])).tolist()
            mask.append(mask_row)
        #Attention
        att_output, att_weights = self.attention(w, torch.from_numpy(np.asarray(mask)).float())
        
        tmaps = (tmaps.unsqueeze_(-1)).expand(list(att_output.size())[0],list(att_output.size())[1],1).float()
        att_output = torch.cat([att_output, tmaps],2)
        
        
        # fc layers
        #w = torch.relu(self.fc1(w)) 
        w = torch.relu(self.fc1(att_output)) 
        w = self.dropout(w)
        
        # final score
        scores = torch.sigmoid(self.fc2(w)) 
                
        return scores, tmaps, wmaps, probs, wmap_lengths, word_sort_ind

word_rnn_dim = 512
char_rnn_dim = 300
dropout = 0.3
fine_tune_word_embeddings = False
target_size = 1
hidden_size = 20
char_emb_dim = 30
charset_size = len(char_map)
char_rnn_layers = 2
word_rnn_layers = 2

model = LM_LSTM_CRF(charset_size, char_emb_dim, char_rnn_dim, char_rnn_layers,
                 lm_vocab_size, word_emb_dim, word_rnn_dim, word_rnn_layers, dropout).to(device)
print(model)
        
model.init_word_embeddings(embeddings.to(device))  # initialize embedding layer with pre-trained embeddings
model.fine_tune_word_embeddings(fine_tune_word_embeddings)  # fine-tune
optimizer = optim.Adam(params=filter(lambda p: p.requires_grad, model.parameters()), lr=0.0001)

loss_fn = nn.BCELoss().to(device)
#loss_fn = nn.KLDivLoss().to(device)

class AverageMeter(object):
    """
    Keeps track of most recent, average, sum, and count of a metric.
    """

    def __init__(self):
        self.reset()

    def reset(self):
        self.val = 0
        self.avg = 0
        self.sum = 0
        self.count = 0

    def update(self, val, n=1):
        self.val = val
        self.sum += val * n
        self.count += n
        self.avg = self.sum / self.count

def train(train_loader, model, loss_fn, optimizer, epoch, print_freq = 25):
    
    model.train()  # training mode enables dropout

    batch_time = AverageMeter()  # forward prop. + back prop. time per batch
    data_time = AverageMeter()  # data loading time per batch
    losses = AverageMeter()  # cross entropy loss
    f1s = AverageMeter()  # f1 score

    start = time.time()

    # Batches
    for i, (wmaps, cmaps_f, cmaps_b, cmarkers_f, cmarkers_b, tmaps, wmap_lengths, cmap_lengths, probs) in enumerate(train_loader):
        
        data_time.update(time.time() - start)
        max_word_len = max(wmap_lengths.tolist())

        # Reduce batch's padded length to maximum in-batch sequence
        # This saves some compute on nn.Linear layers (RNNs are unaffected, since they don't compute over the pads)
        wmaps = wmaps[:, :max_word_len].to(device)
        probs = probs[:, :max_word_len].to(device)
        wmap_lengths = wmap_lengths.to(device)
        cmarkers_f = cmarkers_f[:, :max_word_len].to(device)
        cmarkers_b = cmarkers_b[:, :max_word_len].to(device)
        tmaps = tmaps[:, :max_word_len].to(device)
        
        words = []
        for i in range(len(wmaps)):
            value_to_key = []
            for j in range(len(wmaps[i])):
                value_to_key.append(list(word_map.keys())[list(word_map.values()).index(wmaps.cpu().data.numpy()[i][j])])
            words.append(value_to_key)
        
        # Forward prop.
        scores, tmaps_sorted, wmaps_sorted, probs_sorted, wmap_lengths_sorted, _ = model(words, cmaps_f, cmaps_b, cmarkers_f, cmarkers_b, wmaps, wmap_lengths, cmap_lengths, probs, tmaps)

        # We don't predict the next word at the pads or <end> tokens
        # We will only predict at [dunston, checks, in] among [dunston, checks, in, <end>, <pad>, <pad>, ...]
        # So, prediction lengths are word sequence lengths - 1
        lm_lengths = wmap_lengths_sorted - 1
        lm_lengths = lm_lengths.tolist()
        
        # loss
        probs_sorted.resize_(scores.size())  
        
        scores = pack_padded_sequence(scores, lm_lengths, batch_first=True).data
        targets = pack_padded_sequence(probs_sorted, lm_lengths, batch_first=True).data
        loss = loss_fn(scores,targets)

        # Back prop.
        optimizer.zero_grad()
        loss.backward()

#         grad_clip = True
#         if grad_clip is not None:
#             clip_gradient(optimizer, grad_clip)

        optimizer.step()

        # Keep track of metrics
        losses.update(loss.item(), sum(lm_lengths))
        batch_time.update(time.time() - start)

        start = time.time()
        # Print training status
        if i % print_freq == 0:
            print('Epoch: [{0}][{1}/{2}]\t'
                  'Batch Time {batch_time.val:.3f} ({batch_time.avg:.3f})\t'
                  'Data Load Time {data_time.val:.3f} ({data_time.avg:.3f})\t'
                  'Loss {loss.val:.4f} ({loss.avg:.4f})\t'.format(epoch, i, len(train_loader),
                                                          batch_time=batch_time,
                                                          data_time=data_time, loss=losses))

def intersection(lst1, lst2):
    lst3 = [value for value in lst1 if value in lst2]
    return lst3

def fix_padding(scores_numpy, label_probs,  mask_numpy):
    #if len(scores_numpy) != len(mask_numpy):
    #    print("Error: len(scores_numpy) != len(mask_numpy)")
    #assert len(scores_numpy) == len(mask_numpy)
    #if len(label_probs) != len(mask_numpy):
    #    print("len(label_probs) != len(mask_numpy)")
    #assert len(label_probs) == len(mask_numpy)

    all_scores_no_padd = []
    all_labels_no_pad = []
    for i in range(len(mask_numpy)):
        all_scores_no_padd.append(scores_numpy[i][:mask_numpy[i]])
        all_labels_no_pad.append(label_probs[i][:mask_numpy[i]])

    assert len(all_scores_no_padd) == len(all_labels_no_pad)
    return all_scores_no_padd, all_labels_no_pad

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

            s = np.asarray(s.cpu())
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
            l = l.cpu()
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

epochs = 100
max_score = 0
max_m_scores = []
for epoch in range(0, epochs):
        #model.train(mode=True)
        # One epoch's training
        train(train_loader, model, loss_fn, optimizer, epoch)
        print("\n")
        #Validation
        model.train(mode=False)
        num_m = [0, 0, 0, 0]
        score_m = [0, 0, 0, 0]
        with torch.no_grad():
            for i, ( wmaps, cmaps_f, cmaps_b, cmarkers_f, cmarkers_b, tmaps, wmap_lengths, cmap_lengths, probs) in enumerate(val_loader):

                    
                    max_word_len = max(wmap_lengths.tolist())

                    # Reduce batch's padded length to maximum in-batch sequence
                    # This saves some compute on nn.Linear layers (RNNs are unaffected, since they don't compute over the pads)
                    wmaps = wmaps[:, :max_word_len].to(device)
                    probs = probs[:, :max_word_len].to(device)
                    wmap_lengths = wmap_lengths.to(device)
                    cmarkers_f = cmarkers_f[:, :max_word_len].to(device)
                    cmarkers_b = cmarkers_b[:, :max_word_len].to(device)
                    tmaps = tmaps[:, :max_word_len].to(device)
                    
                    
                    words = []
                    for i in range(len(wmaps)):
                        value_to_key = []
                        for j in range(len(wmaps[i])):
                            value_to_key.append(list(word_map.keys())[list(word_map.values()).index(wmaps.cpu().data.numpy()[i][j])])
                        words.append(value_to_key)

                    # Forward prop.
                    scores, tmaps_sorted, wmaps_sorted, probs_sorted, wmap_lengths_sorted, _ = model(words, cmaps_f, cmaps_b, cmarkers_f, cmarkers_b, wmaps, wmap_lengths, cmap_lengths, probs, tmaps)
                    lm_lengths = wmap_lengths_sorted - 1
                    lm_lengths = lm_lengths.tolist()
                    batch_scores_no_padd, batch_labels_no_pad = fix_padding(scores, probs_sorted, lm_lengths)
                    #print(type(batch_scores_no_padd))
                    batch_num_m, batch_score_m = match_M(batch_scores_no_padd, batch_labels_no_pad)
                    num_m = [sum(i) for i in zip(num_m, batch_num_m)]
                    score_m = [sum(i) for i in zip(score_m, batch_score_m)]

            m_score = [i/j for i,j in zip(score_m, num_m)]
            score = sum(m_score)/len(m_score)
            if score>max_score:
                max_score = score
                max_m_score = m_score
            print(m_score)
            print(max_score)
            print(max_m_score)
print(max_score)
print(max_m_score)

print(max_score)
