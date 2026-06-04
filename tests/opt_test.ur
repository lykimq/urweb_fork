fun id [t ::: Type] (x : t) : t = x

fun main () : transaction page =
    let
        val x = id 42
        val y = id "hello"
    in
        return <xml>{[x]} {[y]}</xml>
    end
