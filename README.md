gcovModified
============

Tweaking the gcov utility for specialized coverage

`list.c` consists of functions designed to manipulate
a linked list structure. The linked list consists of a
`struct List`, which keeps track of the first and last
elements of the list. Elements of the list are represented
by `struct Node`s. A node consists of a pointer to the next
node, and pointers to the key, value, and type of the value
stored by the node. This linked list is designed to output
its data in the form of a JSON object. 

`gcov.c` is an updated version of the `gcov.c` available in
gcc 4.9.0 and it uses the linked list structure to store
elements to be outputted in the `output_intermediate_file`
function. `output_intermediate_file` outputs coverage 
information as JSON objects.
