#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "list.h"

void initList (struct List *list) {
    list->front = NULL;
    list->back = NULL;
}

int isEmptyList (struct List *list) {
    return list->front == NULL;
}

void addToList (struct List *list, char *key, void *value, char *type) {
    struct Node *newNode = malloc(sizeof(struct Node));
   
    if (isEmptyList(list)) {
        list->front = newNode; 
        list->back = newNode;
    }

    else {
        list->back->next = newNode;
        list->back = newNode;
    }

    newNode->key = key;
    newNode->value = value;
    newNode->type = type;
    newNode->next = NULL;
}
static void deleteNode (struct Node *node) {
    int proceed = 1;
    struct Node *next = node->next;
    
    if (next == NULL) {
        proceed = 0;
    }

    if (strcmp(node->type, "list") == 0) {
        deleteList((struct List *) node->value);
    }

        free(node);

    if (proceed) {
        deleteNode(next);
    }
}
        
void deleteList (struct List *list) {
    deleteNode (list->front);
}

static void printNode (struct Node *node) {
    int proceed = 1;
    struct Node *next = node->next;
    
    if (next == NULL) {
        proceed = 0;
    }
    
    if (strcmp(node->type, "list") == 0) {
        printf("%s:[", node->key);
        printList((struct List *) node->value);
        printf("]");
    }
    
    if (strcmp(node->type, "int") == 0) {
       printf("%s:%d", node->key, *(int *) node->value);
    }

    if (strcmp(node->type, "string") == 0) {
        printf("%s:%s", node->key, (char *) node->value);
    }

    if (proceed) {
        printf(",");
        printNode(next);
    }

    fflush(stdout);

}

void printList (struct List *list) {
    printNode (list->front);
}

void printDocument (struct List *list) {
    printf("{");
    printList(list);
    printf("}");
    fflush(stdout);
}

int main() {
     struct List list;
    initList(&list);
    addToList(&list, "h", "1", "int");
    struct List sublist;
    initList(&sublist);
    addToList(&sublist, "hello", "lala", "string");
    addToList(&list, "yo", &sublist, "list");
    addToList(&list, "well", "huh?", "string");
    printf("%s\n", (char *) list.front->value);
    struct Node *next = (list.front)->next;
    printf("%s\n", next->type);
    printf("%s\n", (char *) next->next->value);
    printf("%s\n", (char *) (list).back->value);
    printf("COMMENCING LIST PRINT\n");
    printList(&list);

    deleteList(&list);
  return 0;
} 


