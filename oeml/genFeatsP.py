from rdflib import Graph
from rdflib.namespace import URIRef, SKOS
import argparse
import sys
import os
import csv
import gc
import json

# Argument parsing

def check_n(value):
    ivalue = int(value)
    if ivalue < 3:
        raise argparse.ArgumentTypeError("%s is an invalid ontology snapshots number (min. 3)" % value)
    return ivalue


parser = argparse.ArgumentParser(description="Generates learning dataset from OWL/SKOS versioned datasets")
parser.add_argument('--input', '-i',
                    help = "Input directory path with dataset versions", 
                    required = True)
parser.add_argument('--output', '-o',
                    help = "Output file", 
                    required = True)
parser.add_argument('-n',
                    help = "Number of ontology snapshots (min. 3)",
                    type = check_n,
                    default = 3)
parser.add_argument('--delta-tt', '-dtt',
                    help = "Delta TT parameter, how many versions to skip in evaluation",
                    type = int,
                    required = True)
parser.add_argument('--delta-fc', '-dfc',
                    help = "Delta FC parameter, how many versions to skip in training",
                    type = int,
                    required = True)
parser.add_argument('--top', '-t',
                    help = "URI of the top structural concept",
                    required = True)
parser.add_argument('--str', '-s',
                    help = "URI of the structural property",
                    required = True)
parser.add_argument('--member', '-m',
                    help = "URI of the membership or usage property",
                    required = True)
parser.add_argument('--format', '-f',
                    help = "Serialization format of the input files",
                    choices = ['html', 'hturtle', 'mdata', 'microdata', 'n3', 'nquads', 'nt', 'rdfa', 'rdfa1.0', 'rdfa1.1', 'trix', 'turtle', 'xml'],
                    required = True)
parser.add_argument('--change-definition', '-c',
                    help = "Definition of concept change",
                    choices = ['novelChildren', 'nonEqualChildren', 'childrenParents', 'multiClass', 'extDrift'],
                    required = True)

args = parser.parse_args()

print args.input, args.output, args.n, args.top, args.str, args.member, args.format, args.change_definition, args.delta_tt, args.delta_fc

if args.delta_tt not in range(1, int(args.n) - 2 + 1):
    print "Delta TT must be in range 1-%s" % str(int(args.n) - 2)
    sys.exit()

if args.delta_fc not in range(1, int(args.n) - 1 - int(args.delta_tt) + 1):
    print "Delta FC must be in range 1-%s" % str(int(args.n) - 1 - int(args.delta_tt))
    sys.exit()

if not os.path.exists(args.output):
    os.makedirs(directory)

sys.setrecursionlimit(30000)

def recSKOS(g, h, n):
    structprop = URIRef(args.str)
    if (None, structprop, n) not in g:
        return True
    else: 
        if n not in h:
            h[n] = []
        for s, p, o in g.triples( (None, structprop, n) ):
            if s not in h[n]:
                h[n].append(s)
                recSKOS(g, h, s)

def countChildren(h, n, r):
    if n not in h:
        return 0
    else:
        if r > 0:
            childCounts = []
            for child in h[n]:
                childCounts.append(countChildren(h, child, r - 1))
            return len(h[n]) + sum(childCounts)
        else:
            return len(h[n])

def countSiblings(g, n):
    structprop = URIRef(args.str)
    siblings = []
    for s, p, o in g.triples( (n, structprop, None) ):
        for s2, p2, o2 in g.triples( (None, structprop, o) ):
            siblings.append([s2, p2, o2])
    return len(siblings)

def countParents(g, n):
    structprop = URIRef(args.str)
    parents = []
    for s, p, o in g.triples( (n, structprop, None) ):
        parents.append(o)
    return len(parents)

def countArticles(g, n, dcsubject = URIRef(args.member)):
    # How many articles have n as subject category
    arts = []
    for s, p, o in g.triples( (None, dcsubject, n) ):
        arts.append(s)
    return len(arts)

def countArticlesChildren(g, h, n, r,  dcsubject = URIRef(args.member)):
    # How many articles in this node and r children levels
    if n not in h:
        return countArticles(g, n, dcsubject)
    else:
        if r > 0:
            childCounts = []
            for child in h[n]:
                childCounts.append(countArticlesChildren(g, h, child, r - 1, dcsubject))
            return countArticles(g, n, dcsubject) + sum(childCounts)
        else:
            return countArticles(g, n, dcsubject)

###########
# Snapshots
###########
# Load subdirs from input dir
snapshots = []
for f in os.listdir(args.input):
    if not os.path.isdir(args.input + f):
        snapshots.append(f)

snapshots.sort()

# Only use the specified amount
# DeltaTT indicates how many versions to skip from the end
# for the reference snapshot
# DeltaFC does so for the training snapshots

snapshots = snapshots[len(snapshots) - args.n:]
t_snapshots = snapshots[:-(args.delta_tt + args.delta_fc)]
r_snapshot = snapshots[-(1 + args.delta_tt)]
e_snapshot = snapshots[-1]

print snapshots, t_snapshots, r_snapshot, e_snapshot

# Load the reference dataset

g = Graph()
g.parse(args.input + r_snapshot, format=args.format)

tree = {}
top = URIRef(args.top)

recSKOS(g, tree, top)

print "Dataset %s has %s nodes" % (r_snapshot, str(len(tree)))

print(json.dumps(tree, indent=4))

for ds in t_snapshots:
    # Load sources
    g_o = Graph()
    g_o.parse(args.input + ds, format=args.format)
    
    # Compute tree
    tree_o = {}
    recSKOS(g_o, tree_o, top)

    print "Dataset %s has %s nodes" % (ds, str(len(tree_o)))

    print(json.dumps(tree_o, indent=4))

    with open(args.output + 'feats_' + ds + '.csv', 'wb') as csvfile:
        writer = csv.writer(csvfile, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        # Stack to do a DFS on the hierarchy
        nodeStack = []
        nodeStack.append(top)
        # Set to avoid cycles (i.e. repeating a node)
        doneNodeSet = set()
        while nodeStack:
            node = nodeStack.pop()
            dirChildren = countChildren(tree_o, node, 0)
            dirChildren1 = countChildren(tree_o, node, 1)
            dirChildren2 = countChildren(tree_o, node, 2)
            dirChildren3 = countChildren(tree_o, node, 3)
            numParents = countParents(g_o, node)
            numSiblings = countSiblings(g_o, node)
            dirArticles = countArticles(g_o, node)
            dirArticlesChildren0 = countArticlesChildren(g_o, tree_o, node, 0)
            dirArticlesChildren1 = countArticlesChildren(g_o, tree_o, node, 1)
            dirArticlesChildren2 = countArticlesChildren(g_o, tree_o, node, 2)
            dirArticlesChildren3 = countArticlesChildren(g_o, tree_o, node, 3)
            # Definition of change
            changed = 0
            if not ((node in tree) or (node in tree.values())):
                changed = 1
            if args.change_definition == 'novelChildren':
                if countChildren(tree, node, 0) > countChildren(tree_o, node, 0):
                    changed = 1
            elif args.change_definition == 'nonEqualChildren':
                if not countChildren(tree, node, 0) == countChildren(tree_o, node, 0):
                    changed = 1
            elif args.change_definition == 'childrenParents':
                if not (countChildren(tree, node, 0) == countChildren(tree_o, node, 0) and countParents(g, node) == countParents(g_o, node)):
                    changed = 1
            elif args.change_definition == 'multiClass':
                # Target classes: 0 stable, 1 extended, 2 shrink, 3 lost
                if node in tree or node in tree.values():
                    if countChildren(tree_o, node, 0) == countChildren(tree, node, 0):
                        changed = 0
                    elif countChildren(tree, node, 0) > countChildren(tree_o, node, 0):
                        changed = 1
                    else:
                        changed = 2
                else:
                    changed = 3
            elif args.change_definition == 'extDrift':
                if not countArticles(g_o, node) == countArticles(g, node):
                    changed = 1
            writer.writerow([ str(node).encode('utf-8'),
                              dirChildren,
                              dirChildren1,
                              dirChildren2,
                              dirChildren3,
                              numParents,
                              numSiblings,
                              dirArticles,
                              dirArticlesChildren0,
                              dirArticlesChildren1,
                              dirArticlesChildren2,
                              dirArticlesChildren3,
                              dirArticles / dirChildren if dirChildren > 0 else dirArticles,
                              dirArticlesChildren0 / dirChildren if dirChildren > 0 else dirArticlesChildren0,
                              dirArticlesChildren1 / dirChildren1 if dirChildren1 > 0 else dirArticlesChildren1,
                              dirArticlesChildren2 / dirChildren2 if dirChildren2 > 0 else dirArticlesChildren2,
                              dirArticlesChildren3 / dirChildren3 if dirChildren3 > 0 else dirArticlesChildren3,
                              changed ])
            # We mark this node as done
            doneNodeSet.add(node)
            # If node is not a leaf, process all its children
            if node in tree_o:
                for child in tree_o[node]:
                    # Add this child iff not processed yet
                    if child not in doneNodeSet:
                        nodeStack.append(child)
        # for key in tree_o:
        #     node = key.encode('utf-8')
        #     dirChildren = countChildren(tree_o, key, 0)
        #     dirChildren1 = countChildren(tree_o, key, 1)
        #     dirChildren2 = countChildren(tree_o, key, 2)
        #     dirChildren3 = countChildren(tree_o, key, 3)
        #     numParents = countParents(g_o, key)
        #     numSiblings = countSiblings(g_o, key)
        #     dirArticles = countArticles(g_o, key)
        #     dirArticlesChildren0 = countArticlesChildren(g_o, tree_o, key, 0)
        #     dirArticlesChildren1 = countArticlesChildren(g_o, tree_o, key, 1)
        #     dirArticlesChildren2 = countArticlesChildren(g_o, tree_o, key, 2)
        #     dirArticlesChildren3 = countArticlesChildren(g_o, tree_o, key, 3)
        #     changed = 0 if key in tree and countChildren(tree, key, 0) == countChildren(tree_o, key, 0) and countParents(g, key) == countParents(g_o, key) else 1
        #     writer.writerow([ node, 
        #                       dirChildren, 
        #                       dirChildren1, 
        #                       dirChildren2,
        #                       dirChildren3,
        #                       numParents,
        #                       numSiblings,
        #                       dirArticles,
        #                       dirArticlesChildren0,
        #                       dirArticlesChildren1,
        #                       dirArticlesChildren2,
        #                       dirArticlesChildren3,
        #                       dirArticles / dirChildren if dirChildren > 0 else dirArticles,
        #                       dirArticlesChildren0 / dirChildren if dirChildren > 0 else dirArticlesChildren0,
        #                       dirArticlesChildren1 / dirChildren1 if dirChildren1 > 0 else dirArticlesChildren1,
        #                       dirArticlesChildren2 / dirChildren2 if dirChildren2 > 0 else dirArticlesChildren2,
        #                       dirArticlesChildren3 / dirChildren3 if dirChildren3 > 0 else dirArticlesChildren3,
        #                       changed ])

    # Clean
    g_o = None
    gc.collect()


# Load sources                                                                                                                                       
g_o = Graph()
g_o.parse(args.input + e_snapshot, format=args.format)

# Compute tree                                                                                                                                       
tree_o = {}
recSKOS(g_o, tree_o, top)

print "Dataset %s has %s nodes" % (e_snapshot, str(len(tree)))

print(json.dumps(tree_o, indent=4))

# Write stats on THIS tree, compare last attribute with 3.8 tree                                                                                     
with open(args.output + 'feats_' + e_snapshot + '.csv', 'wb') as csvfile:
    writer = csv.writer(csvfile, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
    # Stack to do a DFS on the hierarchy
    nodeStack = []
    nodeStack.append(top)
    # Set to avoid cycles (i.e. repeating a node)
    doneNodeSet = set()
    while nodeStack:
        node = nodeStack.pop()
        dirChildren = countChildren(tree, node, 0)
        dirChildren1 = countChildren(tree, node, 1)
        dirChildren2 = countChildren(tree, node, 2)
        dirChildren3 = countChildren(tree, node, 3)
        numParents = countParents(g, node)
        numSiblings = countSiblings(g, node)
        dirArticles = countArticles(g, node)
        dirArticlesChildren0 = countArticlesChildren(g, tree, node, 0)
        dirArticlesChildren1 = countArticlesChildren(g, tree, node, 1)
        dirArticlesChildren2 = countArticlesChildren(g, tree, node, 2)
        dirArticlesChildren3 = countArticlesChildren(g, tree, node, 3)
        # Definition of change
        changed = 0
        if not ((node in tree_o) or (node in tree_o.values())):
            changed = 1
        if args.change_definition == 'novelChildren':
            if countChildren(tree_o, node, 0) > countChildren(tree, node, 0):
                changed = 1
        elif args.change_definition == 'nonEqualChildren':
            if not countChildren(tree_o, node, 0) == countChildren(tree, node, 0):
                changed = 1
        elif args.change_definition == 'childrenParents':
            if not (countChildren(tree_o, node, 0) == countChildren(tree, node, 0) and countParents(g_o, node) == countParents(g, node)):
                changed = 1
        elif args.change_definition == 'multiClass':
            # Target classes: 0 stable, 1 extended, 2 shrink, 3 lost
            if node in tree_o or node in tree_o.values():
                if countChildren(tree, node, 0) == countChildren(tree_o, node, 0):
                    changed = 0
                elif countChildren(tree_o, node, 0) > countChildren(tree, node, 0):
                    changed = 1
                else:
                    changed = 2
            else:
                changed = 3
        writer.writerow([ str(node).encode('utf-8'),
                          dirChildren,
                          dirChildren1,
                          dirChildren2,
                          dirChildren3,
                          numParents,
                          numSiblings,
                          dirArticles,
                          dirArticlesChildren0,
                          dirArticlesChildren1,
                          dirArticlesChildren2,
                          dirArticlesChildren3,
                          dirArticles / dirChildren if dirChildren > 0 else dirArticles,
                          dirArticlesChildren0 / dirChildren if dirChildren > 0 else dirArticlesChildren0,
                          dirArticlesChildren1 / dirChildren1 if dirChildren1 > 0 else dirArticlesChildren1,
                          dirArticlesChildren2 / dirChildren2 if dirChildren2 > 0 else dirArticlesChildren2,
                          dirArticlesChildren3 / dirChildren3 if dirChildren3 > 0 else dirArticlesChildren3,
                          changed ])
        # We mark this node as done
        doneNodeSet.add(node)
        # If node is not a leaf, process all its children
        if node in tree:
            for child in tree[node]:
                # Add this child iff not processed yet
                if child not in doneNodeSet:
                    nodeStack.append(child)
    # for key in tree:
    #     node = key.encode('utf-8')
    #     dirChildren = countChildren(tree, key, 0)
    #     dirChildren1 = countChildren(tree, key, 1)
    #     dirChildren2 = countChildren(tree, key, 2)
    #     dirChildren3 = countChildren(tree, key, 3)
    #     numParents = countParents(g, key)
    #     numSiblings = countSiblings(g, key)
    #     dirArticles = countArticles(g, key)
    #     dirArticlesChildren0 = countArticlesChildren(g, tree, key, 0)
    #     dirArticlesChildren1 = countArticlesChildren(g, tree, key, 1)
    #     dirArticlesChildren2 = countArticlesChildren(g, tree, key, 2)
    #     dirArticlesChildren3 = countArticlesChildren(g, tree, key, 3)
    #     changed = 0 if key in tree_o and countChildren(tree_o, key, 0) == countChildren(tree, key, 0) and countParents(g_o, key) == countParents(g, key) else 1
    #     writer.writerow([ node,
    #                       dirChildren, 
    #                       dirChildren1, 
    #                       dirChildren2,
    #                       dirChildren3,
    #                       numParents,
    #                       numSiblings,
    #                       dirArticles,
    #                       dirArticlesChildren0,
    #                       dirArticlesChildren1,
    #                       dirArticlesChildren2,
    #                       dirArticlesChildren3,
    #                       dirArticles / dirChildren if dirChildren > 0 else dirArticles,
    #                       dirArticlesChildren0 / dirChildren if dirChildren > 0 else dirArticlesChildren0,
    #                       dirArticlesChildren1 / dirChildren1 if dirChildren1 > 0 else dirArticlesChildren1,
    #                       dirArticlesChildren2 / dirChildren2 if dirChildren2 > 0 else dirArticlesChildren2,
    #                       dirArticlesChildren3 / dirChildren3 if dirChildren3 > 0 else dirArticlesChildren3,
    #                       changed ])

# Clean                                                                                                                                              
g_o = None
gc.collect()

