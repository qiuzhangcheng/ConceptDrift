##########################################################
# Pastes columns to preserve identity of instances in OEML
##########################################################

args <- commandArgs(trailingOnly = TRUE)

input.files <- head(args,-4)
output.file.training <- head(tail(args,3),1)
output.file.eval <- head(tail(args,2),1)
in.all.snaps <- tail(args,1)

# input.files <- c('feats_1849-hisco.nt.csv', 'feats_1859-hisco.nt.csv', 'feats_1869-hisco.nt.csv', 'feats_1889-hisco.nt.csv', 'feats_1899-hisco.nt.csv', 'feats_1909-hisco.nt.csv')
# output.file.training <- c('training.csv')
# output.file.eval <- c('evaluation.csv')
# in.all.snaps <- T

print(paste("Input file: ", input.files))
print(paste("Output file training: ", output.file.training))
print(paste("Output file evaluation: ", output.file.eval))
print(paste("Terms in all snaps: ", in.all.snaps))

# Read all data files except last (eval dataset)
all <- lapply(input.files, read.csv, header=T)

merged <- data.frame(all[1])

if (length(input.files) > 1) {
    num.feats <- ncol(merged)
    for (i in 2:length(all)) {
        df <- data.frame(all[i])
	colnames(df) <- as.character(seq(1:length(colnames(df))))
        # If all = F, we only consider nodes in all snapshots
        # Otherwise, consider everything and fill with NAs
	print(head(merged))
	print(head(df))
        merged <- merge(merged, df, by.x=1, by.y=1, all = in.all.snaps)
	colnames(merged) <- as.character(seq(1:length(colnames(merged))))
    }

    # List of column numbers where target variables lie
    
    targets <- c()
    for (i in num.feats:length(merged)) {
        if (i %% (num.feats - 1) == 0) {
            targets <- c(targets, i)
        }  
    }
    targets <- targets + 1
    targets <- c(num.feats, targets)

    # Target variable: disjunction between targets
    # If NA is present some change happened
    for (i in targets) {
        merged[is.na(merged[,i]),i] <- 1
    }

    t <- merged[,targets[1]]
    for (i in targets[2:length(targets)]) {
        t <- t + merged[,i]
    }
    t[t > 1] <- 1
    merged <- cbind(merged, t)
    merged$t <- as.character(merged$t)

    # Remove old targets ones
    j <- 0
    for (i in targets) {
        merged[,i - j] <- NULL
        j <- j + 1
    }
}

# Remove instance names
# merged[,1] <- NULL

# Rename features
colnames(merged) <- as.character(seq(1:length(colnames(merged))))

# Save dataset
write.csv(merged, output.file.training, quote = FALSE, na = "", row.names = FALSE)

####################
# Evaluation dataset
####################
eval.dataset <- tail(head(args,-3),1)
# eval.dataset <- c('feats_1930-hisco.nt.csv')
eval <- read.csv(eval.dataset, header=T)

# Remove instance names
# eval[,1] <- NULL
# Save target column, remove
eval.targets <- eval[,ncol(eval)]
eval[,ncol(eval)] <- NULL
ncol(merged)
ncol(eval)

# Add columns as NAs
diff <- ncol(merged) - ncol(eval) - 1
if (diff > 0) {
   eval[as.character(seq(1:diff))] <- NA
}

eval['t'] <- eval.targets

# Rename features
colnames(eval) <- as.character(seq(1:ncol(merged)))

# Save dataset
write.csv(eval, output.file.eval, quote = FALSE, na = "", row.names = FALSE)
