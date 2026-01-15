def reg_to_str(reg: int) -> str:
    if reg == 11:
        return 'fp'
    elif reg == 13:
        return 'sp'
    elif reg == 14:
        return 'lr'
    elif reg == 15:
        return 'pc'
    elif reg > 15:
        return f'v{reg}'
    else:
        return f'r{reg}'
