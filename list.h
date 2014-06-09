struct Node {
    struct Node *next;

    const char *key;
    const void *value;
    const char *type;
};

struct List {
    struct Node *front;
    struct Node *back;
};

void deleteList(struct List *);
void initList(struct List *);
int isEmptyList(struct List *);
void addToList(struct List *, const char *, const void *, 
               const char *);
void deleteList(struct List *);
void printList(struct List *, FILE *);
void printDocument(struct List *, FILE *);
