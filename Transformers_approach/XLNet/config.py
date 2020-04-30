# Defines all paths and model hyperparameters

# Dataset files' paths
train_file = '../../datasets/train.txt'
dev_file = '../../datasets/dev.txt'
test_file = '../../datasets/test.txt'

# Preprocessing variables
# maximum length of sentence after tokenization
MAX_LEN = 72

# model name
model_name = 'xlnet-large-cased'

# Model hyperparameters
xlnet_dim = 25*1024
hidden_dim1 = 1000
hidden_dim2 = 40
final_size = 1

# batch size for training. 
batch_size = 32

# Optimizer parameters
learning_rate = 2e-5
epsilon = 1e-8


num_epochs = 20

max_accuracy = 0
max_match = [0,0,0,0]

val_out = ""
test_out = ""

save_path = '../ensemble/'
# Index of the run of current model, change it after each run
ind = 1
